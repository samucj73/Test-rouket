import streamlit as st
import pandas as pd
import numpy as np
from collections import Counter, deque, defaultdict
import time
from datetime import datetime
import warnings
import plotly.graph_objects as go
import plotly.express as px
warnings.filterwarnings('ignore')

# ========== CONFIGURAÇÕES ==========
class Config:
    HISTORY_SIZE = 2500
    PREDICTION_WINDOW = 10
    TOP_PREDICTIONS = 8
    UPDATE_INTERVAL = 5

# ========== INICIALIZAÇÃO DA SESSÃO ==========
def initialize_session_state():
    if 'roulette_system' not in st.session_state:
        from advanced_roulette_system import RoulettePredictionSystem
        st.session_state.roulette_system = RoulettePredictionSystem()
    
    if 'auto_update' not in st.session_state:
        st.session_state.auto_update = False
    
    if 'last_manual_spin' not in st.session_state:
        st.session_state.last_manual_spin = None

# ========== SISTEMA DE PREDIÇÃO ==========
class AdvancedDataProcessor:
    def __init__(self):
        self.historical_data = []
        self.recent_numbers = deque(maxlen=100)
        self.number_stats = {i: {'count': 0, 'last_seen': 0, 'gap': 0} for i in range(37)}
        self.spin_count = 0
        self.patterns = defaultdict(list)
        
    def add_spin(self, number):
        """Adiciona um novo sorteio com análise completa"""
        self.spin_count += 1
        self.historical_data.append(number)
        self.recent_numbers.append(number)
        
        # Atualiza estatísticas do número
        self.number_stats[number]['gap'] = self.spin_count - self.number_stats[number]['last_seen']
        self.number_stats[number]['last_seen'] = self.spin_count
        self.number_stats[number]['count'] += 1
        
        # Detecta padrões
        self._detect_patterns()
    
    def _detect_patterns(self):
        """Detecta padrões complexos nos dados"""
        if len(self.historical_data) < 10:
            return
            
        recent = list(self.recent_numbers)
        
        # Padrão de repetição
        if len(recent) >= 2 and recent[-1] == recent[-2]:
            self.patterns['double_repeat'].append(recent[-1])
        
        # Padrão de alternância
        if len(recent) >= 3:
            if recent[-1] != recent[-2] and recent[-2] != recent[-3]:
                self.patterns['alternating'].append(recent[-1])
    
    def get_advanced_analysis(self):
        """Retorna análise estatística avançada"""
        if self.spin_count == 0:
            return {}
            
        return {
            'hot_numbers': self._get_hot_numbers(period=50),
            'cold_numbers': self._get_cold_numbers(),
            'overdue_numbers': self._get_overdue_numbers(),
            'frequency_trend': self._get_frequency_trend(),
            'gap_analysis': self._get_gap_analysis(),
            'pattern_analysis': self._get_pattern_analysis(),
            'cluster_analysis': self._get_cluster_analysis()
        }
    
    def _get_hot_numbers(self, period=50):
        """Identifica números quentes"""
        if len(self.recent_numbers) < period:
            period = len(self.recent_numbers)
        recent_counts = Counter(list(self.recent_numbers)[-period:])
        return dict(recent_counts.most_common(10))
    
    def _get_cold_numbers(self):
        """Identifica números frios"""
        counts = {num: stats['count'] for num, stats in self.number_stats.items()}
        sorted_counts = sorted(counts.items(), key=lambda x: x[1])
        return dict(sorted_counts[:10])
    
    def _get_overdue_numbers(self):
        """Identifica números em atraso"""
        gaps = {num: stats['gap'] for num, stats in self.number_stats.items()}
        sorted_gaps = sorted(gaps.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_gaps[:10])
    
    def _get_frequency_trend(self):
        """Analisa tendência de frequência"""
        if len(self.historical_data) < 20:
            return {}
        
        recent = self.historical_data[-20:]
        earlier = self.historical_data[-40:-20] if len(self.historical_data) >= 40 else self.historical_data[:-20]
        
        recent_freq = Counter(recent)
        earlier_freq = Counter(earlier)
        
        trend = {}
        for num in range(37):
            recent_count = recent_freq.get(num, 0)
            earlier_count = earlier_freq.get(num, 0)
            trend[num] = recent_count - earlier_count
            
        return trend
    
    def _get_gap_analysis(self):
        """Analisa padrões de gaps"""
        gaps = {}
        for num in range(37):
            gap = self.number_stats[num]['gap']
            if self.number_stats[num]['count'] > 0:
                actual_avg_gap = self.spin_count / self.number_stats[num]['count']
                gaps[num] = {
                    'current_gap': gap,
                    'expected_gap': actual_avg_gap,
                    'deviation': gap - actual_avg_gap
                }
        return gaps
    
    def _get_pattern_analysis(self):
        """Analisa padrões detectados"""
        pattern_strength = {}
        for pattern_type, numbers in self.patterns.items():
            if numbers:
                recent_pattern = Counter(numbers[-10:])
                pattern_strength[pattern_type] = dict(recent_pattern)
        return pattern_strength
    
    def _get_cluster_analysis(self):
        """Analisa clusters de números"""
        wheel_layout = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        
        recent_clusters = []
        for num in list(self.recent_numbers)[-20:]:
            if num in wheel_layout:
                idx = wheel_layout.index(num)
                cluster = [
                    wheel_layout[(idx-1) % len(wheel_layout)],
                    wheel_layout[idx],
                    wheel_layout[(idx+1) % len(wheel_layout)]
                ]
                recent_clusters.extend(cluster)
        
        cluster_freq = Counter(recent_clusters)
        return dict(cluster_freq.most_common(10))

class AdvancedPredictionModel:
    def __init__(self, data_processor):
        self.data_processor = data_processor
        self.prediction_history = []
        
    def predict(self):
        """Gera predições usando múltiplas estratégias"""
        if self.data_processor.spin_count < 10:
            return self._get_random_predictions()
            
        analysis = self.data_processor.get_advanced_analysis()
        
        strategies = {
            'hot_numbers': self._strategy_hot_numbers(analysis),
            'overdue_numbers': self._strategy_overdue_numbers(analysis),
            'pattern_based': self._strategy_pattern_based(analysis),
            'gap_based': self._strategy_gap_based(analysis),
            'cluster_based': self._strategy_cluster_based(analysis),
            'trend_based': self._strategy_trend_based(analysis)
        }
        
        final_scores = self._combine_strategies(strategies)
        final_scores = self._apply_final_adjustments(final_scores)
        
        sorted_predictions = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
        predictions = sorted_predictions[:Config.TOP_PREDICTIONS]
        self.prediction_history.append(predictions)
        
        return predictions
    
    def _strategy_hot_numbers(self, analysis):
        scores = {}
        hot_numbers = analysis.get('hot_numbers', {})
        total_hot_spins = sum(hot_numbers.values()) or 1
        
        for num, count in hot_numbers.items():
            scores[num] = (count / total_hot_spins) * 0.25
        return scores
    
    def _strategy_overdue_numbers(self, analysis):
        scores = {}
        overdue_nums = analysis.get('overdue_numbers', {})
        max_gap = max(overdue_nums.values()) if overdue_nums else 1
        
        for num, gap in overdue_nums.items():
            normalized_gap = gap / max_gap
            scores[num] = normalized_gap * 0.20
        return scores
    
    def _strategy_pattern_based(self, analysis):
        scores = {}
        patterns = analysis.get('pattern_analysis', {})
        
        for pattern_type, pattern_data in patterns.items():
            weight = 0.15
            if 'repeat' in pattern_type:
                weight = 0.18
            elif 'alternating' in pattern_type:
                weight = 0.12
                
            for num, count in pattern_data.items():
                scores[num] = scores.get(num, 0) + (count * weight)
        return scores
    
    def _strategy_gap_based(self, analysis):
        scores = {}
        gap_analysis = analysis.get('gap_analysis', {})
        
        for num, gap_data in gap_analysis.items():
            deviation = gap_data.get('deviation', 0)
            if deviation > 0:
                scores[num] = min(deviation / 37, 1.0) * 0.15
        return scores
    
    def _strategy_cluster_based(self, analysis):
        scores = {}
        clusters = analysis.get('cluster_analysis', {})
        total_cluster = sum(clusters.values()) or 1
        
        for num, count in clusters.items():
            scores[num] = (count / total_cluster) * 0.12
        return scores
    
    def _strategy_trend_based(self, analysis):
        scores = {}
        trends = analysis.get('frequency_trend', {})
        
        for num, trend in trends.items():
            if trend > 0:
                scores[num] = min(trend / 5, 1.0) * 0.10
        return scores
    
    def _combine_strategies(self, strategies):
        combined_scores = {}
        for strategy_scores in strategies.values():
            for num, score in strategy_scores.items():
                combined_scores[num] = combined_scores.get(num, 0) + score
        return combined_scores
    
    def _apply_final_adjustments(self, scores):
        recent_numbers = list(self.data_processor.recent_numbers)[-3:]
        for num in recent_numbers:
            if num in scores:
                scores[num] *= 0.3
                
        for num in scores:
            stats = self.data_processor.number_stats[num]
            if stats['count'] > 0:
                expected_frequency = self.data_processor.spin_count / stats['count']
                current_gap = stats['gap']
                if current_gap > expected_frequency * 0.8:
                    scores[num] *= 1.2
        return scores
    
    def _get_random_predictions(self):
        numbers = list(range(37))
        np.random.shuffle(numbers)
        return [(num, 0.1) for num in numbers[:Config.TOP_PREDICTIONS]]
    
    def get_accuracy(self):
        if len(self.prediction_history) < 10:
            return 0
            
        correct_predictions = 0
        total_predictions = 0
        
        for i, predictions in enumerate(self.prediction_history[-10:]):
            if i < len(self.data_processor.historical_data) - 1:
                actual_number = self.data_processor.historical_data[i + 1]
                predicted_numbers = [pred[0] for pred in predictions]
                if actual_number in predicted_numbers:
                    correct_predictions += 1
                total_predictions += 1
                
        return correct_predictions / total_predictions if total_predictions > 0 else 0

class RoulettePredictionSystem:
    def __init__(self):
        self.data_processor = AdvancedDataProcessor()
        self.prediction_model = AdvancedPredictionModel(self.data_processor)
        self.performance_stats = {
            'total_predictions': 0,
            'correct_predictions': 0,
            'accuracy_history': []
        }
        
    def add_spin(self, number):
        """Processa um novo sorteio"""
        self.data_processor.add_spin(number)
        
        # Gera novas predições
        predictions = self.prediction_model.predict()
        
        # Atualiza estatísticas de acurácia
        self._update_accuracy(number)
        
        current_accuracy = self.prediction_model.get_accuracy()
        self.performance_stats['accuracy_history'].append(current_accuracy)
        
        return predictions
    
    def _update_accuracy(self, actual_number):
        """Atualiza estatísticas de acurácia"""
        if len(self.prediction_model.prediction_history) > 0:
            last_predictions = self.prediction_model.prediction_history[-1]
            predicted_numbers = [pred[0] for pred in last_predictions]
            
            if actual_number in predicted_numbers:
                self.performance_stats['correct_predictions'] += 1
            self.performance_stats['total_predictions'] += 1

    def get_system_status(self):
        return {
            'total_spins': self.data_processor.spin_count,
            'current_accuracy': self.prediction_model.get_accuracy(),
            'recent_numbers': list(self.data_processor.recent_numbers),
            'performance_stats': self.performance_stats,
            'last_update': datetime.now().isoformat()
        }

# ========== INTERFACE STREAMLIT ==========
def main():
    st.set_page_config(
        page_title="Sistema de Predição - Roleta", 
        page_icon="🎰", 
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    initialize_session_state()
    system = st.session_state.roulette_system
    
    # CSS personalizado
    st.markdown("""
    <style>
    .prediction-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        margin: 5px;
    }
    .number-badge {
        display: inline-block;
        background: #ff6b6b;
        color: white;
        padding: 8px 12px;
        border-radius: 20px;
        margin: 2px;
        font-weight: bold;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #667eea;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🎰 Sistema Avançado de Predição - Roleta")
        st.markdown("---")
    
    # Sidebar para controles
    with st.sidebar:
        st.header("🎮 Controles do Sistema")
        
        st.subheader("Adicionar Sorteio")
        manual_number = st.number_input("Número (0-36):", min_value=0, max_value=36, value=0)
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🎯 Adicionar Sorteio", use_container_width=True):
                predictions = system.add_spin(int(manual_number))
                st.session_state.last_manual_spin = manual_number
                st.success(f"Sorteio {manual_number} adicionado!")
        
        with col_btn2:
            if st.button("🎲 Sorteio Aleatório", use_container_width=True):
                random_number = np.random.randint(0, 37)
                predictions = system.add_spin(random_number)
                st.session_state.last_manual_spin = random_number
                st.success(f"Sorteio aleatório: {random_number}")
        
        st.markdown("---")
        st.subheader("Configurações")
        
        # Auto-update simulation
        st.session_state.auto_update = st.checkbox("Simular Sorteios Automáticos", value=False)
        if st.session_state.auto_update:
            update_interval = st.slider("Intervalo (segundos):", 2, 10, 5)
            if st.button("⏹️ Parar Simulação"):
                st.session_state.auto_update = False
                st.rerun()
        else:
            if st.button("▶️ Iniciar Simulação"):
                st.session_state.auto_update = True
                st.rerun()
        
        st.markdown("---")
        st.subheader("Estatísticas Rápidas")
        status = system.get_system_status()
        st.metric("Total de Sorteios", status['total_spins'])
        st.metric("Acurácia Atual", f"{status['current_accuracy']:.2%}")
        st.metric("Previsões Corretas", status['performance_stats']['correct_predictions'])
    
    # Auto-update simulation
    if st.session_state.auto_update:
        time.sleep(Config.UPDATE_INTERVAL)
        random_number = np.random.randint(0, 37)
        system.add_spin(random_number)
        st.rerun()
    
    # Métricas principais
    status = system.get_system_status()
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🎯 Total de Sorteios", status['total_spins'])
    with col2:
        st.metric("📊 Acurácia Atual", f"{status['current_accuracy']:.2%}")
    with col3:
        st.metric("✅ Previsões Corretas", 
                 status['performance_stats']['correct_predictions'],
                 f"{status['performance_stats']['correct_predictions']}/{status['performance_stats']['total_predictions']}")
    with col4:
        st.metric("🕒 Última Atualização", datetime.now().strftime("%H:%M:%S"))
    
    st.markdown("---")
    
    # Seção de Previsões Atuais
    st.header("🎲 Próximos Números Prováveis")
    
    if system.data_processor.spin_count > 0:
        predictions = system.prediction_model.predict()
        
        # Display das previsões
        cols = st.columns(len(predictions))
        for i, (num, confidence) in enumerate(predictions):
            with cols[i]:
                confidence_pct = confidence * 100
                color = "#ff6b6b" if confidence_pct > 15 else "#4ecdc4" if confidence_pct > 10 else "#45b7d1"
                
                st.markdown(f"""
                <div class="prediction-card" style="background: {color};">
                    <h3 style="margin:0; font-size: 2em;">{num}</h3>
                    <p style="margin:0; font-size: 0.9em;">{confidence_pct:.1f}% confiança</p>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Adicione o primeiro sorteio para ver as previsões.")
    
    st.markdown("---")
    
    # Layout de duas colunas para análise
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        # Gráfico de Acurácia
        st.subheader("📈 Desempenho do Sistema")
        if len(status['performance_stats']['accuracy_history']) > 1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                y=status['performance_stats']['accuracy_history'],
                mode='lines+markers',
                name='Acurácia',
                line=dict(color='#667eea', width=3)
            ))
            fig.update_layout(
                title="Evolução da Acurácia",
                xaxis_title="Número de Previsões",
                yaxis_title="Acurácia",
                template="plotly_white",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Acurácia será plotada aqui após previsões suficientes.")
        
        # Últimos Sorteios
        st.subheader("📊 Histórico Recente")
        if status['recent_numbers']:
            recent_display = status['recent_numbers'][-15:]
            html_numbers = " ".join([f'<span class="number-badge">{num}</span>' for num in recent_display])
            st.markdown(f'<div style="text-align: center;">{html_numbers}</div>', unsafe_allow_html=True)
        else:
            st.info("Nenhum sorteio registrado ainda.")
    
    with col_right:
        # Análise Detalhada
        st.subheader("🔍 Análise em Tempo Real")
        
        if system.data_processor.spin_count > 0:
            analysis = system.data_processor.get_advanced_analysis()
            
            with st.expander("🔥 Números Quentes", expanded=True):
                hot_numbers = analysis.get('hot_numbers', {})
                for num, count in list(hot_numbers.items())[:5]:
                    st.write(f"**{num}**: {count} vezes (últimos 50 sorteios)")
            
            with st.expander("❄️ Números Atrasados"):
                overdue_numbers = analysis.get('overdue_numbers', {})
                for num, gap in list(overdue_numbers.items())[:5]:
                    st.write(f"**{num}**: {gap} sorteios atrás")
            
            with st.expander("📈 Tendências"):
                trends = analysis.get('frequency_trend', {})
                positive_trends = {k: v for k, v in trends.items() if v > 0}
                if positive_trends:
                    for num, trend in list(positive_trends.items())[:3]:
                        st.write(f"**{num}**: +{trend} (frequência aumentando)")
                else:
                    st.write("Sem tendências positivas significativas")
                    
        else:
            st.info("Adicione sorteios para ver a análise detalhada.")
    
    # Seção de Análise Estatística Avançada
    st.markdown("---")
    st.header("📊 Análise Estatística Completa")
    
    if system.data_processor.spin_count > 10:
        col1, col2 = st.columns(2)
        
        with col1:
            # Distribuição de Frequência
            st.subheader("📋 Distribuição de Frequência")
            all_numbers = list(range(37))
            counts = [system.data_processor.number_stats[num]['count'] for num in all_numbers]
            
            fig = px.bar(
                x=all_numbers, 
                y=counts,
                labels={'x': 'Número', 'y': 'Frequência'},
                title="Frequência de Todos os Números"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Análise de Gaps
            st.subheader("⏱️ Análise de Gaps")
            gaps = [system.data_processor.number_stats[num]['gap'] for num in range(37)]
            avg_gap = sum(gaps) / len(gaps) if gaps else 0
            
            fig = go.Figure(data=[go.Histogram(x=gaps, nbinsx=20)])
            fig.update_layout(
                title=f"Distribuição de Gaps (Média: {avg_gap:.1f})",
                xaxis_title="Gap desde última aparição",
                yaxis_title="Quantidade de Números"
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Coletando dados suficientes para análise estatística completa...")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
        <p>Sistema de análise preditiva para roleta - Desenvolvido para fins educacionais</p>
        <p>🎯 Versão 2.0 - Algoritmo Avançado de Predição</p>
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
```

🚀 PRINCIPAIS CORREÇÕES E MELHORIAS:

1. Compatibilidade com Streamlit Cloud:

· ✅ Remove completamente o Flask
· ✅ Usa session_state do Streamlit para persistência
· ✅ Interface nativa do Streamlit
· ✅ Auto-atualização sem conflitos

2. Interface Melhorada:

· ✅ Design moderno com gradientes
· ✅ Gráficos interativos com Plotly
· ✅ Layout responsivo
· ✅ Visualização de dados em tempo real

3. Funcionalidades Adicionadas:

· ✅ Simulação automática de sorteios
· ✅ Análise estatística visual
· ✅ Histórico interativo
· ✅ Métricas em tempo real

4. Otimizações de Performance:

· ✅ Controle de atualização automática
· ✅ Cálculos eficientes
· ✅ Gerenciamento de estado otimizado

🎯 COMO USAR:

1. Execute no Streamlit Cloud:

```bash
streamlit run seu_arquivo.py
```

1. Controles Disponíveis:
   · Adicionar sorteios manuais
   · Sorteios aleatórios para teste
   · Simulação automática
   · Configurações em tempo real
2. Monitoramento:
   · Acurácia em tempo real
   · Análise estatística completa
   · Gráficos interativos
   · Histórico detalhado
