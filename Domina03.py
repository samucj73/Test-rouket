import pandas as pd
import numpy as np
from collections import Counter, deque, defaultdict
import requests
import time
from threading import Thread
from flask import Flask, render_template, jsonify
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ========== CONFIGURAÇÕES AVANÇADAS ==========
class Config:
    API_URL = "https://sua-api.com/live"
    API_KEY = "seu_token_aqui"
    HISTORY_SIZE = 2500
    PREDICTION_WINDOW = 10
    TOP_PREDICTIONS = 8
    UPDATE_INTERVAL = 30

# ========== PROCESSADOR DE DADOS AVANÇADO ==========
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
            
        analysis = {
            'hot_numbers': self._get_hot_numbers(period=50),
            'cold_numbers': self._get_cold_numbers(),
            'overdue_numbers': self._get_overdue_numbers(),
            'frequency_trend': self._get_frequency_trend(),
            'gap_analysis': self._get_gap_analysis(),
            'pattern_analysis': self._get_pattern_analysis(),
            'cluster_analysis': self._get_cluster_analysis()
        }
        return analysis
    
    def _get_hot_numbers(self, period=50):
        """Identifica números quentes (mais frequentes no período recente)"""
        if len(self.recent_numbers) < period:
            period = len(self.recent_numbers)
        recent_counts = Counter(list(self.recent_numbers)[-period:])
        return dict(recent_counts.most_common(10))
    
    def _get_cold_numbers(self):
        """Identifica números frios (menos frequentes globalmente)"""
        counts = {num: stats['count'] for num, stats in self.number_stats.items()}
        sorted_counts = sorted(counts.items(), key=lambda x: x[1])
        return dict(sorted_counts[:10])
    
    def _get_overdue_numbers(self):
        """Identifica números em atraso (maior gap desde última aparição)"""
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
        """Analisa padrões de gaps entre repetições"""
        gaps = {}
        for num in range(37):
            gap = self.number_stats[num]['gap']
            avg_gap = 37  # Gap esperado teórico
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
                recent_pattern = Counter(numbers[-10:])  # Últimos 10 padrões
                pattern_strength[pattern_type] = dict(recent_pattern)
                
        return pattern_strength
    
    def _get_cluster_analysis(self):
        """Analisa clusters de números (vizinhos na roleta)"""
        # Layout da roleta europeia
        wheel_layout = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
        
        recent_clusters = []
        for num in list(self.recent_numbers)[-20:]:
            if num in wheel_layout:
                idx = wheel_layout.index(num)
                # Pega vizinhos no layout
                cluster = [
                    wheel_layout[(idx-1) % len(wheel_layout)],
                    wheel_layout[idx],
                    wheel_layout[(idx+1) % len(wheel_layout)]
                ]
                recent_clusters.extend(cluster)
        
        cluster_freq = Counter(recent_clusters)
        return dict(cluster_freq.most_common(10))

# ========== MODELO DE PREDIÇÃO AVANÇADO ==========
class AdvancedPredictionModel:
    def __init__(self, data_processor):
        self.data_processor = data_processor
        self.prediction_history = []
        
    def predict(self):
        """Gera predições usando múltiplas estratégias"""
        if self.data_processor.spin_count < 10:
            return self._get_random_predictions()
            
        analysis = self.data_processor.get_advanced_analysis()
        
        # Combina múltiplas estratégias
        strategies = {
            'hot_numbers': self._strategy_hot_numbers(analysis),
            'overdue_numbers': self._strategy_overdue_numbers(analysis),
            'pattern_based': self._strategy_pattern_based(analysis),
            'gap_based': self._strategy_gap_based(analysis),
            'cluster_based': self._strategy_cluster_based(analysis),
            'trend_based': self._strategy_trend_based(analysis)
        }
        
        # Combina resultados com pesos
        final_scores = self._combine_strategies(strategies)
        
        # Aplica ajustes finais
        final_scores = self._apply_final_adjustments(final_scores)
        
        # Ordena por score
        sorted_predictions = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
        
        predictions = sorted_predictions[:Config.TOP_PREDICTIONS]
        self.prediction_history.append(predictions)
        
        return predictions
    
    def _strategy_hot_numbers(self, analysis):
        """Estratégia baseada em números quentes"""
        scores = {}
        hot_numbers = analysis.get('hot_numbers', {})
        total_hot_spins = sum(hot_numbers.values()) or 1
        
        for num, count in hot_numbers.items():
            scores[num] = (count / total_hot_spins) * 0.25
            
        return scores
    
    def _strategy_overdue_numbers(self, analysis):
        """Estratégia baseada em números atrasados"""
        scores = {}
        overdue_nums = analysis.get('overdue_numbers', {})
        max_gap = max(overdue_nums.values()) if overdue_nums else 1
        
        for num, gap in overdue_nums.items():
            # Normaliza o gap e aplica peso
            normalized_gap = gap / max_gap
            scores[num] = normalized_gap * 0.20
            
        return scores
    
    def _strategy_pattern_based(self, analysis):
        """Estratégia baseada em padrões detectados"""
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
        """Estratégia baseada em análise de gaps"""
        scores = {}
        gap_analysis = analysis.get('gap_analysis', {})
        
        for num, gap_data in gap_analysis.items():
            deviation = gap_data.get('deviation', 0)
            if deviation > 0:  # Número está atrasado
                scores[num] = min(deviation / 37, 1.0) * 0.15
                
        return scores
    
    def _strategy_cluster_based(self, analysis):
        """Estratégia baseada em clusters na roleta"""
        scores = {}
        clusters = analysis.get('cluster_analysis', {})
        total_cluster = sum(clusters.values()) or 1
        
        for num, count in clusters.items():
            scores[num] = (count / total_cluster) * 0.12
            
        return scores
    
    def _strategy_trend_based(self, analysis):
        """Estratégia baseada em tendências de frequência"""
        scores = {}
        trends = analysis.get('frequency_trend', {})
        
        for num, trend in trends.items():
            if trend > 0:  # Frequência aumentando
                scores[num] = min(trend / 5, 1.0) * 0.10
                
        return scores
    
    def _combine_strategies(self, strategies):
        """Combina todas as estratégias com pesos"""
        combined_scores = {}
        
        for strategy_name, strategy_scores in strategies.items():
            for num, score in strategy_scores.items():
                combined_scores[num] = combined_scores.get(num, 0) + score
                
        return combined_scores
    
    def _apply_final_adjustments(self, scores):
        """Aplica ajustes finais nas predições"""
        # Penaliza números que saíram muito recentemente
        recent_numbers = list(self.data_processor.recent_numbers)[-3:]
        for num in recent_numbers:
            if num in scores:
                scores[num] *= 0.3  # Reduz significativamente
                
        # Bonus para números com boa relação frequência/gap
        for num in scores:
            stats = self.data_processor.number_stats[num]
            if stats['count'] > 0:
                expected_frequency = self.data_processor.spin_count / stats['count']
                current_gap = stats['gap']
                if current_gap > expected_frequency * 0.8:
                    scores[num] *= 1.2
                    
        return scores
    
    def _get_random_predictions(self):
        """Predições iniciais quando não há dados suficientes"""
        numbers = list(range(37))
        np.random.shuffle(numbers)
        return [(num, 0.1) for num in numbers[:Config.TOP_PREDICTIONS]]
    
    def get_accuracy(self):
        """Calcula acurácia das predições recentes"""
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

# ========== API CLIENT ==========
class RouletteAPIClient:
    def __init__(self):
        self.last_result = None
        self.connected = False
        
    def connect(self):
        """Simula conexão com API - substitua com sua API real"""
        try:
            # headers = {'Authorization': f'Bearer {Config.API_KEY}'}
            # response = requests.get(Config.API_URL, headers=headers, timeout=10)
            # self.last_result = response.json()
            self.connected = True
            print("✅ Conectado à API de roleta")
            return True
        except Exception as e:
            print(f"❌ Erro na conexão: {e}")
            self.connected = False
            return False
    
    def get_live_result(self):
        """Obtém resultado ao vivo - substitua com sua API real"""
        if not self.connected:
            return None
            
        try:
            # headers = {'Authorization': f'Bearer {Config.API_KEY}'}
            # response = requests.get(Config.API_URL, headers=headers, timeout=10)
            # result = response.json()
            
            # SIMULAÇÃO - substitua pela chamada real da sua API
            result = {
                'number': np.random.randint(0, 37),
                'timestamp': datetime.now().isoformat(),
                'color': 'red' if np.random.random() > 0.5 else 'black'
            }
            
            self.last_result = result
            return result
            
        except Exception as e:
            print(f"❌ Erro ao obter resultado: {e}")
            return None

# ========== SISTEMA PRINCIPAL ==========
class RoulettePredictionSystem:
    def __init__(self):
        self.data_processor = AdvancedDataProcessor()
        self.prediction_model = AdvancedPredictionModel(self.data_processor)
        self.api_client = RouletteAPIClient()
        self.is_running = False
        self.performance_stats = {
            'total_predictions': 0,
            'correct_predictions': 0,
            'accuracy_history': []
        }
        
    def start(self):
        """Inicia o sistema de predição"""
        print("🚀 Iniciando Sistema de Predição de Roleta...")
        
        if not self.api_client.connect():
            print("❌ Falha na conexão com a API")
            return False
            
        self.is_running = True
        self._start_monitoring()
        return True
    
    def _start_monitoring(self):
        """Inicia monitoramento em tempo real"""
        def monitor_loop():
            while self.is_running:
                result = self.api_client.get_live_result()
                if result and result != self.api_client.last_result:
                    self._process_new_result(result)
                    
                time.sleep(Config.UPDATE_INTERVAL)
        
        monitor_thread = Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        print("📡 Monitoramento ativo...")
    
    def _process_new_result(self, result):
        """Processa novo resultado da roleta"""
        number = result['number']
        timestamp = result['timestamp']
        
        print(f"🎯 Novo sorteio: {number} - {timestamp}")
        
        # Adiciona aos dados
        self.data_processor.add_spin(number)
        
        # Verifica acurácia da última predição
        self._update_accuracy(number)
        
        # Gera novas predições
        predictions = self.prediction_model.predict()
        
        # Atualiza estatísticas
        self.performance_stats['total_predictions'] += 1
        current_accuracy = self.prediction_model.get_accuracy()
        self.performance_stats['accuracy_history'].append(current_accuracy)
        
        print(f"📊 Predições: {[p[0] for p in predictions]}")
        print(f"🎯 Acurácia atual: {current_accuracy:.2%}")
        print("-" * 50)
    
    def _update_accuracy(self, actual_number):
        """Atualiza estatísticas de acurácia"""
        if len(self.prediction_model.prediction_history) > 0:
            last_predictions = self.prediction_model.prediction_history[-1]
            predicted_numbers = [pred[0] for pred in last_predictions]
            
            if actual_number in predicted_numbers:
                self.performance_stats['correct_predictions'] += 1
    
    def get_system_status(self):
        """Retorna status completo do sistema"""
        return {
            'is_running': self.is_running,
            'total_spins': self.data_processor.spin_count,
            'current_accuracy': self.prediction_model.get_accuracy(),
            'recent_numbers': list(self.data_processor.recent_numbers),
            'performance_stats': self.performance_stats,
            'last_update': datetime.now().isoformat()
        }

# ========== APLICAÇÃO WEB ==========
app = Flask(__name__)
prediction_system = RoulettePredictionSystem()

@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sistema de Predição - Roleta</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { 
                font-family: Arial, sans-serif; 
                margin: 20px; 
                background: #f5f5f5;
            }
            .container { 
                max-width: 1200px; 
                margin: 0 auto; 
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .status { 
                padding: 15px; 
                margin: 10px 0; 
                border-radius: 5px; 
                background: #e8f4fd;
                border-left: 4px solid #2196F3;
            }
            .predictions { 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(80px, 1fr)); 
                gap: 10px; 
                margin: 20px 0;
            }
            .pred-number { 
                padding: 15px; 
                text-align: center; 
                background: #4CAF50; 
                color: white; 
                border-radius: 5px;
                font-weight: bold;
                font-size: 18px;
            }
            .stats-grid { 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
                gap: 15px; 
                margin: 20px 0;
            }
            .stat-card { 
                padding: 15px; 
                background: #f8f9fa; 
                border-radius: 5px;
                text-align: center;
            }
            .number-history { 
                display: flex; 
                flex-wrap: wrap; 
                gap: 5px; 
                margin: 10px 0;
            }
            .history-number { 
                padding: 8px 12px; 
                background: #ddd; 
                border-radius: 3px;
                font-size: 14px;
            }
            .history-number.recent { 
                background: #ffeb3b; 
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎯 Sistema de Predição - Roleta</h1>
            
            <div class="status" id="status">
                Carregando...
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Total de Sorteios</h3>
                    <div id="total-spins">0</div>
                </div>
                <div class="stat-card">
                    <h3>Acurácia Atual</h3>
                    <div id="accuracy">0%</div>
                </div>
                <div class="stat-card">
                    <h3>Previsões Corretas</h3>
                    <div id="correct-predictions">0</div>
                </div>
                <div class="stat-card">
                    <h3>Status</h3>
                    <div id="system-status">Offline</div>
                </div>
            </div>
            
            <h2>🎲 Próximos Números Prováveis</h2>
            <div class="predictions" id="predictions">
                <!-- Previsões serão inseridas aqui -->
            </div>
            
            <h2>📊 Últimos Sorteios</h2>
            <div class="number-history" id="recent-numbers">
                <!-- Histórico será inserido aqui -->
            </div>
            
            <div style="margin-top: 30px; text-align: center; color: #666;">
                <p>Sistema de análise preditiva para roleta - Desenvolvido para fins educacionais</p>
            </div>
        </div>

        <script>
            function updateDashboard() {
                fetch('/api/status')
                    .then(response => response.json())
                    .then(data => {
                        // Atualiza status
                        document.getElementById('status').innerHTML = 
                            `<strong>Status:</strong> ${data.is_running ? 'Online' : 'Offline'} | 
                             <strong>Última atualização:</strong> ${new Date(data.last_update).toLocaleTimeString()}`;
                        
                        // Atualiza estatísticas
                        document.getElementById('total-spins').textContent = data.total_spins;
                        document.getElementById('accuracy').textContent = (data.current_accuracy * 100).toFixed(1) + '%';
                        document.getElementById('correct-predictions').textContent = data.performance_stats.correct_predictions;
                        document.getElementById('system-status').textContent = data.is_running ? 'Online' : 'Offline';
                        
                        // Atualiza previsões
                        const predictionsDiv = document.getElementById('predictions');
                        predictionsDiv.innerHTML = '';
                        
                        if (data.predictions) {
                            data.predictions.forEach(pred => {
                                const predElem = document.createElement('div');
                                predElem.className = 'pred-number';
                                predElem.textContent = pred[0];
                                predElem.title = `Confiança: ${(pred[1] * 100).toFixed(1)}%`;
                                predictionsDiv.appendChild(predElem);
                            });
                        }
                        
                        // Atualiza histórico
                        const historyDiv = document.getElementById('recent-numbers');
                        historyDiv.innerHTML = '';
                        
                        if (data.recent_numbers) {
                            data.recent_numbers.slice(-15).forEach(num => {
                                const numElem = document.createElement('div');
                                numElem.className = 'history-number';
                                numElem.textContent = num;
                                historyDiv.appendChild(numElem);
                            });
                        }
                    })
                    .catch(error => {
                        console.error('Erro ao atualizar dashboard:', error);
                    });
            }
            
            // Atualiza a cada 5 segundos
            setInterval(updateDashboard, 5000);
            updateDashboard();
            
            // Inicia o sistema quando a página carregar
            fetch('/api/start', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    console.log('Sistema iniciado:', data);
                });
        </script>
    </body>
    </html>
    """

@app.route('/api/status')
def api_status():
    status = prediction_system.get_system_status()
    
    # Adiciona predições atuais
    if prediction_system.data_processor.spin_count > 0:
        predictions = prediction_system.prediction_model.predict()
        status['predictions'] = predictions
    else:
        status['predictions'] = []
    
    return jsonify(status)

@app.route('/api/start', methods=['POST'])
def api_start():
    success = prediction_system.start()
    return jsonify({'success': success, 'message': 'Sistema iniciado'})

@app.route('/api/add_test_spin/<int:number>')
def api_add_test_spin(number):
    """Rota para testes - adiciona sorteio simulado"""
    if 0 <= number <= 36:
        prediction_system.data_processor.add_spin(number)
        return jsonify({'success': True, 'number': number})
    return jsonify({'success': False, 'error': 'Número inválido'})

if __name__ == '__main__':
    print("=" * 60)
    print("🎰 SISTEMA DE PREDIÇÃO DE ROLETA - v2.0 AVANÇADO")
    print("=" * 60)
    print("📊 Características do sistema:")
    print("   • 6 Estratégias de predição combinadas")
    print("   • Análise de padrões complexos")
    print("   • Detecção de hot/cold numbers")
    print("   • Análise de clusters na roleta")
    print("   • Monitoramento em tempo real")
    print("   • Dashboard web interativo")
    print("=" * 60)
    
    # Inicia o servidor
    app.run(debug=True, host='0.0.0.0', port=5000)
