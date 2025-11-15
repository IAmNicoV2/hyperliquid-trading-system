"""
Serveur Web Flask pour le monitoring des signaux Hyperliquid en temps réel
"""

import sys
import os

# Configuration de l'encodage UTF-8 pour Windows (sans modifier sys.stdout directement)
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from flask import Flask, render_template_string, jsonify
from flask_cors import CORS
import threading
import time
from datetime import datetime
from hyperliquid_signals import HyperliquidSignalGenerator
import json
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# État global
generator = None
current_analysis = None
signal_history = []
monitoring_active = False
monitor_thread = None

def init_generator(coin="BTC", interval="5m"):
    """Initialise le générateur de signaux"""
    global generator
    try:
        generator = HyperliquidSignalGenerator(coin=coin, interval=interval)
        candles = generator.fetch_historical_candles(limit=200)
        if not candles:
            logger.warning(f"Aucun chandelier récupéré pour {coin}/{interval}")
        else:
            logger.info(f"✅ Générateur initialisé: {coin}/{interval} ({len(candles)} chandeliers)")
        return generator
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation du générateur: {e}", exc_info=True)
        return None

def monitor_signals():
    """Thread de monitoring continu"""
    global current_analysis, signal_history, monitoring_active
    
    while monitoring_active:
        try:
            if generator:
                # Recharger les données
                generator.fetch_historical_candles(limit=200)
                
                # Analyser
                analysis = generator.analyze()
                
                # Sauvegarder dans l'historique (garder les 100 derniers)
                signal_history.append(analysis)
                if len(signal_history) > 100:
                    signal_history.pop(0)
                
                current_analysis = analysis
                
        except Exception as e:
            logger.error(f"Erreur dans le monitoring: {e}", exc_info=True)
        
        time.sleep(30)  # Mise à jour toutes les 30 secondes

@app.route('/')
def index():
    """Page principale"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/signal')
def get_signal():
    """API pour obtenir le signal actuel"""
    global current_analysis
    
    if not generator:
        init_generator()
    
    # Forcer une nouvelle analyse pour avoir les données à jour
    try:
        generator.fetch_historical_candles(limit=200)
        current_analysis = generator.analyze()
        
        # Vérifier que advanced_analysis est présent
        if current_analysis and 'advanced_analysis' not in current_analysis:
            logger.warning("⚠️ Attention: advanced_analysis manquant dans l'analyse")
            logger.debug(f"Clés disponibles: {list(current_analysis.keys())}")
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse: {e}", exc_info=True)
    
    return jsonify(current_analysis if current_analysis else {})

@app.route('/api/history')
def get_history():
    """API pour obtenir l'historique des signaux"""
    return jsonify(signal_history[-50:])  # Derniers 50 signaux

@app.route('/api/start_monitoring')
def start_monitoring():
    """Démarre le monitoring"""
    global monitoring_active, monitor_thread
    
    if not monitoring_active:
        if not generator:
            init_generator()
        
        monitoring_active = True
        monitor_thread = threading.Thread(target=monitor_signals, daemon=True)
        monitor_thread.start()
        
        return jsonify({'status': 'started', 'message': 'Monitoring démarré'})
    
    return jsonify({'status': 'already_running', 'message': 'Monitoring déjà actif'})

@app.route('/api/stop_monitoring')
def stop_monitoring():
    """Arrête le monitoring"""
    global monitoring_active
    
    monitoring_active = False
    return jsonify({'status': 'stopped', 'message': 'Monitoring arrêté'})

@app.route('/api/config', methods=['POST'])
def update_config():
    """Met à jour la configuration"""
    global generator, current_analysis
    
    from flask import request
    data = request.json
    
    coin = data.get('coin', 'BTC')
    interval = data.get('interval', '5m')
    
    init_generator(coin=coin, interval=interval)
    current_analysis = generator.analyze()
    
    return jsonify({'status': 'updated', 'coin': coin, 'interval': interval})

# Template HTML
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hyperliquid - Monitoring Signaux Trading</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {
            background: linear-gradient(135deg, #0a0e1a 0%, #1a1f2e 100%);
            color: #e4e6eb;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }
        .signal-badge {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 18px;
        }
        .signal-buy {
            background: rgba(34, 197, 94, 0.2);
            color: #22c55e;
            border: 2px solid #22c55e;
            box-shadow: 0 0 20px rgba(34, 197, 94, 0.3);
        }
        .signal-sell {
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
            border: 2px solid #ef4444;
            box-shadow: 0 0 20px rgba(239, 68, 68, 0.3);
        }
        .signal-neutral {
            background: rgba(156, 163, 175, 0.2);
            color: #9ca3af;
            border: 2px solid #9ca3af;
        }
        .metric-card {
            background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
            border: 1px solid #374151;
            border-radius: 12px;
            padding: 20px;
            transition: all 0.3s ease;
        }
        .metric-card:hover {
            border-color: #4b5563;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        .pulsing {
            animation: pulse 2s ease-in-out infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .chart-container {
            background: #1a1f2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #374151;
        }
    </style>
</head>
<body class="min-h-screen p-4 md:p-6">
    <div class="max-w-7xl mx-auto">
        <!-- En-tête -->
        <div class="mb-6">
            <h1 class="text-4xl md:text-5xl font-bold mb-2 bg-gradient-to-r from-green-400 via-blue-400 to-purple-500 bg-clip-text text-transparent">
                🚀 Hyperliquid Trading Signals
            </h1>
            <p class="text-gray-400">Monitoring en temps réel avec Stop Loss & Take Profit</p>
        </div>

        <!-- Contrôles -->
        <div class="mb-6 p-4 bg-gray-800 rounded-lg border border-gray-700">
            <div class="flex flex-wrap gap-4 items-center">
                <button id="startBtn" onclick="startMonitoring()" class="px-6 py-2 bg-green-600 hover:bg-green-700 rounded-lg font-semibold">
                    ▶️ Démarrer Monitoring
                </button>
                <button id="stopBtn" onclick="stopMonitoring()" class="px-6 py-2 bg-red-600 hover:bg-red-700 rounded-lg font-semibold" disabled>
                    ⏹️ Arrêter
                </button>
                <span id="status" class="px-4 py-2 bg-gray-700 rounded-lg">
                    ⏸️ Arrêté
                </span>
                <span id="lastUpdate" class="text-gray-400 text-sm ml-auto"></span>
            </div>
        </div>

        <!-- Signal Principal -->
        <div id="signalCard" class="mb-6 p-6 bg-gradient-to-r from-gray-800 to-gray-900 rounded-xl border-2 border-gray-700">
            <div class="flex flex-col md:flex-row items-center justify-between gap-4">
                <div>
                    <div class="text-gray-400 text-sm mb-2">🎯 Signal de Trading</div>
                    <div id="signalDisplay" class="signal-badge signal-neutral">
                        Chargement...
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-gray-400 text-sm mb-1">Prix Actuel</div>
                    <div id="currentPrice" class="text-white font-bold text-3xl md:text-4xl">
                        $0.00
                    </div>
                </div>
            </div>
        </div>

        <!-- SL/TP -->
        <div id="slTpCard" class="mb-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="metric-card">
                <div class="text-red-400 text-sm mb-2">🛡️ Stop Loss</div>
                <div id="stopLoss" class="text-white font-bold text-2xl">$0.00</div>
                <div id="stopLossPercent" class="text-red-400 text-sm mt-1">-0.00%</div>
            </div>
            <div class="metric-card">
                <div class="text-green-400 text-sm mb-2">🎯 Take Profit</div>
                <div id="takeProfit" class="text-white font-bold text-2xl">$0.00</div>
                <div id="takeProfitPercent" class="text-green-400 text-sm mt-1">+0.00%</div>
            </div>
        </div>

        <!-- Indicateurs -->
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
            <div class="metric-card">
                <div class="text-gray-400 text-xs mb-1">RSI (14)</div>
                <div id="rsi" class="font-bold text-xl">0.0</div>
            </div>
            <div class="metric-card">
                <div class="text-gray-400 text-xs mb-1">MACD</div>
                <div id="macd" class="font-bold text-xl">0.0000</div>
            </div>
            <div class="metric-card">
                <div class="text-gray-400 text-xs mb-1">EMA 20</div>
                <div id="ema20" class="font-bold text-xl">$0</div>
            </div>
            <div class="metric-card">
                <div class="text-gray-400 text-xs mb-1">EMA 50</div>
                <div id="ema50" class="font-bold text-xl">$0</div>
            </div>
            <div class="metric-card">
                <div class="text-gray-400 text-xs mb-1">Order Flow</div>
                <div id="orderFlow" class="font-bold text-xl">0.0%</div>
            </div>
            <div class="metric-card">
                <div class="text-gray-400 text-xs mb-1">Risk/Reward</div>
                <div id="riskReward" class="font-bold text-xl">0.00</div>
            </div>
        </div>

        <!-- Analyse Avancée -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <!-- Volatilité et Momentum -->
            <div class="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 class="text-lg font-semibold mb-4">📊 Volatilité & Momentum</h3>
                <div class="space-y-3">
                    <div>
                        <div class="text-gray-400 text-sm mb-1">Régime de Volatilité</div>
                        <div id="volatilityRegime" class="text-white font-bold text-xl">-</div>
                        <div id="volatilityPercent" class="text-gray-400 text-xs mt-1"></div>
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <div class="text-gray-400 text-xs mb-1">ATR</div>
                            <div id="atr" class="text-blue-400 font-semibold">$0</div>
                        </div>
                        <div>
                            <div class="text-gray-400 text-xs mb-1">Momentum</div>
                            <div id="momentum" class="text-purple-400 font-semibold">0%</div>
                        </div>
                    </div>
                    <div id="squeezeAlert" class="hidden p-2 bg-yellow-900 border border-yellow-600 rounded text-yellow-300 text-sm">
                        ⚡ SQUEEZE détecté - Breakout imminent!
                    </div>
                </div>
            </div>

            <!-- Order Book Analysis -->
            <div class="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 class="text-lg font-semibold mb-4">🔍 Analyse du Carnet d'Ordres</h3>
                <div class="space-y-3">
                    <div id="wallInfo" class="hidden p-3 bg-blue-900 border border-blue-600 rounded">
                        <div class="text-blue-300 font-semibold text-sm mb-1" id="wallTitle">Mur détecté</div>
                        <div class="text-white text-xs" id="wallDetails"></div>
                    </div>
                    <div>
                        <div class="text-gray-400 text-xs mb-1">Déséquilibre</div>
                        <div id="orderBookImbalance" class="text-white font-semibold">0%</div>
                    </div>
                    <div>
                        <div class="text-gray-400 text-xs mb-1">Supports (Order Book)</div>
                        <div id="obSupports" class="text-green-400 text-sm">-</div>
                    </div>
                    <div>
                        <div class="text-gray-400 text-xs mb-1">Résistances (Order Book)</div>
                        <div id="obResistances" class="text-red-400 text-sm">-</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Niveaux Clés et Patterns -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            <!-- Niveaux Clés -->
            <div class="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 class="text-lg font-semibold mb-4">🎯 Niveaux Clés</h3>
                <div class="space-y-3">
                    <div>
                        <div class="text-gray-400 text-xs mb-1">Pivot Point</div>
                        <div id="pivot" class="text-yellow-400 font-semibold">$0</div>
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <div class="text-gray-400 text-xs mb-1">R1</div>
                            <div id="r1" class="text-red-400 text-sm">$0</div>
                        </div>
                        <div>
                            <div class="text-gray-400 text-xs mb-1">S1</div>
                            <div id="s1" class="text-green-400 text-sm">$0</div>
                        </div>
                    </div>
                    <div>
                        <div class="text-gray-400 text-xs mb-1">Supports Techniques</div>
                        <div id="techSupports" class="text-green-400 text-sm">-</div>
                    </div>
                    <div>
                        <div class="text-gray-400 text-xs mb-1">Résistances Techniques</div>
                        <div id="techResistances" class="text-red-400 text-sm">-</div>
                    </div>
                </div>
            </div>

            <!-- Patterns et Divergences -->
            <div class="bg-gray-800 rounded-lg p-6 border border-gray-700">
                <h3 class="text-lg font-semibold mb-4">🕯️ Patterns & Divergences</h3>
                <div class="space-y-3">
                    <div id="candlestickPatterns">
                        <div class="text-gray-400 text-xs mb-2">Patterns de Chandeliers</div>
                        <div id="patternsList" class="text-sm text-gray-300">Aucun pattern détecté</div>
                    </div>
                    <div id="divergenceInfo" class="hidden p-3 bg-purple-900 border border-purple-600 rounded">
                        <div class="text-purple-300 font-semibold text-sm mb-1">⚠️ DIVERGENCE</div>
                        <div class="text-white text-xs" id="divergenceDesc"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Signaux de Scalping -->
        <div id="scalpingSignalsCard" class="mb-6 bg-gradient-to-r from-purple-900 to-blue-900 rounded-lg p-6 border border-purple-700">
            <h3 class="text-lg font-semibold mb-4">⚡ Signaux de Scalping</h3>
            <div id="scalpingSignals" class="space-y-2">
                <div class="text-gray-300 text-sm">Aucun signal de scalping actif</div>
            </div>
            <div class="mt-4 pt-4 border-t border-purple-700">
                <div class="flex items-center gap-2">
                    <span class="text-gray-400 text-sm">Confiance:</span>
                    <span id="confidence" class="px-3 py-1 rounded font-semibold text-sm">-</span>
                </div>
            </div>
        </div>

        <!-- Suggestions de Trades avec SL/TP -->
        <div id="tradesSuggestionsCard" class="mb-6 bg-gradient-to-r from-green-900 to-blue-900 rounded-lg p-6 border border-green-700">
            <h3 class="text-lg font-semibold mb-4">💼 Suggestions de Trades</h3>
            <div id="tradesSuggestions" class="space-y-3">
                <div class="text-gray-300 text-sm">Aucune suggestion de trade disponible</div>
            </div>
        </div>

        <!-- Graphique -->
        <div class="chart-container mb-6">
            <canvas id="priceChart"></canvas>
        </div>

        <!-- Historique des Signaux -->
        <div class="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 class="text-xl font-semibold mb-4">📊 Historique des Signaux</h3>
            <div id="historyTable" class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr class="border-b border-gray-700">
                            <th class="text-left p-2">Heure</th>
                            <th class="text-left p-2">Signal</th>
                            <th class="text-left p-2">Prix</th>
                            <th class="text-left p-2">RSI</th>
                            <th class="text-left p-2">Force</th>
                        </tr>
                    </thead>
                    <tbody id="historyBody">
                        <tr><td colspan="5" class="text-center p-4 text-gray-500">Aucun signal enregistré</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        let priceChart = null;
        let updateInterval = null;

        // Initialiser le graphique
        function initChart() {
            const ctx = document.getElementById('priceChart').getContext('2d');
            priceChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Prix BTC',
                        data: [],
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            labels: { color: '#e4e6eb' }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: '#9ca3af' },
                            grid: { color: '#374151' }
                        },
                        y: {
                            ticks: { color: '#9ca3af', callback: function(value) { return '$' + value.toLocaleString(); } },
                            grid: { color: '#374151' }
                        }
                    }
                }
            });
        }

        // Mettre à jour l'affichage
        function updateDisplay(data) {
            try {
                if (!data || typeof data !== 'object') {
                    console.error('Données invalides:', data);
                    return;
                }
                
                // Signal
                const signalEl = document.getElementById('signalDisplay');
                if (!signalEl) {
                    console.error('Élément signalDisplay non trouvé');
                    return;
                }
                
                const signal = data.signal || 'NEUTRE';
                signalEl.className = 'signal-badge ' + 
                    (signal === 'ACHAT' ? 'signal-buy' : 
                     signal === 'VENTE' ? 'signal-sell' : 'signal-neutral');
                signalEl.textContent = signal === 'ACHAT' ? '📈 ACHAT' : 
                                      signal === 'VENTE' ? '📉 VENTE' : '⚖️ NEUTRE';
            
                // Prix
                const priceEl = document.getElementById('currentPrice');
                if (priceEl && data.current_price) {
                    priceEl.textContent = 
                        '$' + parseFloat(data.current_price).toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                }
            
                // SL/TP
                if (data.sl_tp && data.sl_tp.stop_loss > 0) {
                document.getElementById('stopLoss').textContent = 
                    '$' + data.sl_tp.stop_loss.toLocaleString('fr-FR', {minimumFractionDigits: 2});
                document.getElementById('stopLossPercent').textContent = 
                    (data.signal === 'ACHAT' ? '-' : '+') + data.sl_tp.stop_loss_percent.toFixed(2) + '%';
                
                document.getElementById('takeProfit').textContent = 
                    '$' + data.sl_tp.take_profit.toLocaleString('fr-FR', {minimumFractionDigits: 2});
                document.getElementById('takeProfitPercent').textContent = 
                    (data.signal === 'ACHAT' ? '+' : '-') + data.sl_tp.take_profit_percent.toFixed(2) + '%';
                
                document.getElementById('riskReward').textContent = 
                    '1:' + data.sl_tp.risk_reward.toFixed(2);
            }
            
            // Indicateurs
            const ind = data.indicators;
            document.getElementById('rsi').textContent = ind.rsi.toFixed(1);
            document.getElementById('macd').textContent = ind.macd.histogram.toFixed(4);
            document.getElementById('ema20').textContent = '$' + ind.ema20.toLocaleString('fr-FR', {minimumFractionDigits: 0});
            document.getElementById('ema50').textContent = '$' + ind.ema50.toLocaleString('fr-FR', {minimumFractionDigits: 0});
            document.getElementById('orderFlow').textContent = ind.order_flow_imbalance.toFixed(1) + '%';
            
            // Analyse Avancée
            if (data.advanced_analysis) {
                const adv = data.advanced_analysis;
                
                // Volatilité
                if (adv.volatility) {
                    const vol = adv.volatility;
                    const regime = vol.regime || 'unknown';
                    const regimeText = regime === 'high' ? 'ÉLEVÉE' : regime === 'low' ? 'FAIBLE' : 'NORMALE';
                    const regimeColor = regime === 'high' ? 'text-red-400' : regime === 'low' ? 'text-blue-400' : 'text-yellow-400';
                    document.getElementById('volatilityRegime').textContent = regimeText;
                    document.getElementById('volatilityRegime').className = 'text-white font-bold text-xl ' + regimeColor;
                    document.getElementById('volatilityPercent').textContent = vol.volatility_percent ? vol.volatility_percent.toFixed(3) + '%' : '';
                    
                    if (vol.atr_value) {
                        document.getElementById('atr').textContent = '$' + vol.atr_value.toLocaleString('fr-FR', {minimumFractionDigits: 0});
                    }
                    
                    // Squeeze
                    if (vol.squeeze) {
                        document.getElementById('squeezeAlert').classList.remove('hidden');
                    } else {
                        document.getElementById('squeezeAlert').classList.add('hidden');
                    }
                }
                
                // Momentum
                if (adv.momentum) {
                    const mom = adv.momentum;
                    const momentumText = mom.momentum_percent ? mom.momentum_percent.toFixed(3) + '%' : '0%';
                    const momentumColor = mom.momentum_percent > 0 ? 'text-green-400' : 'text-red-400';
                    document.getElementById('momentum').textContent = momentumText;
                    document.getElementById('momentum').className = 'text-purple-400 font-semibold ' + momentumColor;
                }
                
                // Nouveaux indicateurs rapides
                if (adv.stochastic) {
                    // Afficher dans la console pour debug
                    console.log('Stochastic:', adv.stochastic);
                }
                if (adv.williams_r !== undefined) {
                    console.log('Williams %R:', adv.williams_r);
                }
                if (adv.cci !== undefined) {
                    console.log('CCI:', adv.cci);
                }
                if (adv.price_action && adv.price_action.length > 0) {
                    console.log('Price Action Signals:', adv.price_action);
                }
                
                // Order Book
                if (adv.order_book) {
                    const ob = adv.order_book;
                    document.getElementById('orderBookImbalance').textContent = 
                        (ob.order_book_imbalance || 0).toFixed(1) + '%';
                    
                    if (ob.wall_detected) {
                        const wallSide = ob.wall_side === 'support' ? '🛡️ Support' : '🚧 Résistance';
                        const wallColor = ob.wall_side === 'support' ? 'bg-green-900 border-green-600' : 'bg-red-900 border-red-600';
                        document.getElementById('wallInfo').className = 'p-3 ' + wallColor + ' border rounded';
                        document.getElementById('wallTitle').textContent = wallSide + ' détecté';
                        document.getElementById('wallDetails').textContent = 
                            `Prix: $${ob.wall_price.toLocaleString('fr-FR', {minimumFractionDigits: 2})} | Taille: ${ob.wall_size.toFixed(2)}`;
                        document.getElementById('wallInfo').classList.remove('hidden');
                    } else {
                        document.getElementById('wallInfo').classList.add('hidden');
                    }
                    
                    if (ob.support_levels && ob.support_levels.length > 0) {
                        document.getElementById('obSupports').textContent = 
                            ob.support_levels.slice(0, 3).map(s => '$' + s.toLocaleString('fr-FR', {minimumFractionDigits: 0})).join(', ');
                    } else {
                        if (ob.error) {
                            document.getElementById('obSupports').textContent = 'Non disponible';
                            document.getElementById('obSupports').className = 'text-gray-500 text-sm';
                        } else {
                            document.getElementById('obSupports').textContent = '-';
                        }
                    }
                    
                    if (ob.resistance_levels && ob.resistance_levels.length > 0) {
                        document.getElementById('obResistances').textContent = 
                            ob.resistance_levels.slice(0, 3).map(r => '$' + r.toLocaleString('fr-FR', {minimumFractionDigits: 0})).join(', ');
                    } else {
                        if (ob.error) {
                            document.getElementById('obResistances').textContent = 'Non disponible';
                            document.getElementById('obResistances').className = 'text-gray-500 text-sm';
                        } else {
                            document.getElementById('obResistances').textContent = '-';
                        }
                    }
                } else {
                    // Si order_book n'existe pas, afficher un message
                    document.getElementById('orderBookImbalance').textContent = 'N/A';
                    document.getElementById('obSupports').textContent = 'Chargement...';
                    document.getElementById('obResistances').textContent = 'Chargement...';
                }
                
                // Niveaux Clés
                if (adv.key_levels) {
                    const kl = adv.key_levels;
                    if (kl.pivot_points) {
                        const pp = kl.pivot_points;
                        if (pp.pivot) {
                            document.getElementById('pivot').textContent = '$' + pp.pivot.toLocaleString('fr-FR', {minimumFractionDigits: 2});
                        }
                        if (pp.r1) {
                            document.getElementById('r1').textContent = '$' + pp.r1.toLocaleString('fr-FR', {minimumFractionDigits: 0});
                        }
                        if (pp.s1) {
                            document.getElementById('s1').textContent = '$' + pp.s1.toLocaleString('fr-FR', {minimumFractionDigits: 0});
                        }
                    }
                    
                    if (kl.supports && kl.supports.length > 0) {
                        document.getElementById('techSupports').textContent = 
                            kl.supports.slice(0, 3).map(s => '$' + s.toLocaleString('fr-FR', {minimumFractionDigits: 0})).join(', ');
                    } else {
                        document.getElementById('techSupports').textContent = '-';
                    }
                    
                    if (kl.resistances && kl.resistances.length > 0) {
                        document.getElementById('techResistances').textContent = 
                            kl.resistances.slice(0, 3).map(r => '$' + r.toLocaleString('fr-FR', {minimumFractionDigits: 0})).join(', ');
                    } else {
                        document.getElementById('techResistances').textContent = '-';
                    }
                }
                
                // Patterns de Chandeliers
                if (adv.candlestick_patterns && adv.candlestick_patterns.length > 0) {
                    const patternsHtml = adv.candlestick_patterns.map(p => {
                        const emoji = p.signal === 'BUY' ? '📈' : p.signal === 'SELL' ? '📉' : '⚖️';
                        const color = p.signal === 'BUY' ? 'text-green-400' : p.signal === 'SELL' ? 'text-red-400' : 'text-gray-400';
                        return `<div class="${color} mb-1">${emoji} ${p.pattern}: ${p.description}</div>`;
                    }).join('');
                    document.getElementById('patternsList').innerHTML = patternsHtml;
                } else {
                    document.getElementById('patternsList').textContent = 'Aucun pattern détecté';
                    document.getElementById('patternsList').className = 'text-sm text-gray-400';
                }
                
                // Divergence
                if (adv.divergence) {
                    const div = adv.divergence;
                    const divColor = div.signal === 'BUY' ? 'bg-green-900 border-green-600' : 'bg-red-900 border-red-600';
                    document.getElementById('divergenceInfo').className = 'p-3 ' + divColor + ' border rounded';
                    document.getElementById('divergenceDesc').textContent = div.description || '';
                    document.getElementById('divergenceInfo').classList.remove('hidden');
                } else {
                    document.getElementById('divergenceInfo').classList.add('hidden');
                }
            }
            
            // Signaux de Scalping
            if (data.signal_details && data.signal_details.scalping_signals) {
                const scalping = data.signal_details.scalping_signals;
                if (scalping.length > 0) {
                    const scalpingHtml = scalping.map(sig => 
                        `<div class="p-2 bg-gray-800 rounded border border-gray-700 text-sm">${sig}</div>`
                    ).join('');
                    document.getElementById('scalpingSignals').innerHTML = scalpingHtml;
                } else {
                    document.getElementById('scalpingSignals').innerHTML = 
                        '<div class="text-gray-300 text-sm">Aucun signal de scalping actif</div>';
                }
            }
            
            // Confiance
            if (data.signal_details && data.signal_details.confidence) {
                const conf = data.signal_details.confidence;
                const confColor = conf === 'high' ? 'bg-green-600' : conf === 'medium' ? 'bg-yellow-600' : 'bg-red-600';
                const confText = conf === 'high' ? '🟢 HAUTE' : conf === 'medium' ? '🟡 MOYENNE' : '🔴 FAIBLE';
                document.getElementById('confidence').textContent = confText;
                document.getElementById('confidence').className = 'px-3 py-1 rounded font-semibold text-sm ' + confColor;
            }
            
            // Suggestions de Trades avec SL/TP
            if (data.signal && data.signal !== 'NEUTRE' && data.sl_tp && data.sl_tp.stop_loss > 0) {
                const tradeType = data.signal === 'ACHAT' ? 'LONG' : 'SHORT';
                const tradeColor = data.signal === 'ACHAT' ? 'border-green-500 bg-green-900' : 'border-red-500 bg-red-900';
                const tradeIcon = data.signal === 'ACHAT' ? '📈' : '📉';
                
                const tradeHtml = `
                    <div class="p-4 ${tradeColor} border-2 rounded-lg">
                        <div class="flex items-center justify-between mb-3">
                            <div class="flex items-center gap-2">
                                <span class="text-2xl">${tradeIcon}</span>
                                <div>
                                    <div class="font-bold text-lg text-white">${tradeType}</div>
                                    <div class="text-xs text-gray-300">Prix d'entrée: $${parseFloat(data.current_price).toLocaleString('fr-FR', {minimumFractionDigits: 2})}</div>
                                </div>
                            </div>
                            <div class="text-right">
                                <div class="text-xs text-gray-300 mb-1">Confiance</div>
                                <div class="font-semibold ${data.signal_details.confidence === 'high' ? 'text-green-400' : data.signal_details.confidence === 'medium' ? 'text-yellow-400' : 'text-red-400'}">
                                    ${data.signal_details.confidence ? data.signal_details.confidence.toUpperCase() : 'MEDIUM'}
                                </div>
                            </div>
                        </div>
                        <div class="grid grid-cols-2 gap-3 mt-3">
                            <div class="bg-black bg-opacity-30 p-2 rounded">
                                <div class="text-xs text-gray-400 mb-1">🛡️ Stop Loss</div>
                                <div class="text-red-300 font-bold">$${data.sl_tp.stop_loss.toLocaleString('fr-FR', {minimumFractionDigits: 2})}</div>
                                <div class="text-xs text-red-400">${data.signal === 'ACHAT' ? '-' : '+'}${data.sl_tp.stop_loss_percent.toFixed(2)}%</div>
                            </div>
                            <div class="bg-black bg-opacity-30 p-2 rounded">
                                <div class="text-xs text-gray-400 mb-1">🎯 Take Profit</div>
                                <div class="text-green-300 font-bold">$${data.sl_tp.take_profit.toLocaleString('fr-FR', {minimumFractionDigits: 2})}</div>
                                <div class="text-xs text-green-400">${data.signal === 'ACHAT' ? '+' : '-'}${data.sl_tp.take_profit_percent.toFixed(2)}%</div>
                            </div>
                        </div>
                        <div class="mt-3 pt-3 border-t border-gray-600">
                            <div class="grid grid-cols-2 gap-2 mb-2">
                                <div class="flex justify-between text-xs">
                                    <span class="text-gray-400">Risk/Reward:</span>
                                    <span class="text-yellow-400 font-semibold">1:${data.sl_tp.risk_reward.toFixed(2)}</span>
                                </div>
                                <div class="flex justify-between text-xs">
                                    <span class="text-gray-400">Frais:</span>
                                    <span class="text-orange-400 font-semibold">${(data.sl_tp.total_fees_percent || 0).toFixed(3)}%</span>
                                </div>
                            </div>
                            ${data.sl_tp.break_even ? `
                            <div class="text-xs text-gray-400 mt-2">
                                Break-even: $${data.sl_tp.break_even.toLocaleString('fr-FR', {minimumFractionDigits: 2})}
                            </div>
                            ` : ''}
                            ${data.signal_details.scalping_signals && data.signal_details.scalping_signals.length > 0 ? 
                                `<div class="mt-2 text-xs text-gray-300">
                                    <div class="font-semibold mb-1">Signaux actifs:</div>
                                    <div class="space-y-1">
                                        ${data.signal_details.scalping_signals.slice(0, 3).map(s => `<div>• ${s}</div>`).join('')}
                                    </div>
                                </div>` : ''
                            }
                        </div>
                    </div>
                `;
                document.getElementById('tradesSuggestions').innerHTML = tradeHtml;
            } else {
                document.getElementById('tradesSuggestions').innerHTML = 
                    '<div class="text-gray-300 text-sm">Aucune suggestion de trade disponible (signal NEUTRE ou SL/TP non calculés)</div>';
            }
            
            // Graphique
            if (data.candles && data.candles.length > 0) {
                const prices = data.candles.map(c => c.close);
                const times = data.candles.map(c => new Date(c.time * 1000).toLocaleTimeString('fr-FR'));
                
                priceChart.data.labels = times;
                priceChart.data.datasets[0].data = prices;
                priceChart.update('none');
            }
            
                // Dernière mise à jour
                const lastUpdateEl = document.getElementById('lastUpdate');
                if (lastUpdateEl) {
                    lastUpdateEl.textContent = 
                        'Dernière mise à jour: ' + new Date().toLocaleTimeString('fr-FR');
                }
            } catch (error) {
                console.error('Erreur dans updateDisplay:', error);
            }
        }

        // Charger le signal
        async function loadSignal() {
            try {
                const response = await fetch('/api/signal');
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                console.log('Données reçues:', data);
                updateDisplay(data);
            } catch (error) {
                console.error('Erreur lors du chargement:', error);
                document.getElementById('signalDisplay').textContent = 'Erreur de chargement';
                document.getElementById('signalDisplay').className = 'signal-badge signal-neutral';
            }
        }

        // Démarrer le monitoring
        async function startMonitoring() {
            try {
                await fetch('/api/start_monitoring');
                document.getElementById('startBtn').disabled = true;
                document.getElementById('stopBtn').disabled = false;
                document.getElementById('status').textContent = '🟢 Actif';
                document.getElementById('status').className = 'px-4 py-2 bg-green-600 rounded-lg pulsing';
                
                // Mettre à jour toutes les 5 secondes
                if (updateInterval) clearInterval(updateInterval);
                updateInterval = setInterval(loadSignal, 5000);
                loadSignal();
            } catch (error) {
                console.error('Erreur:', error);
            }
        }

        // Arrêter le monitoring
        async function stopMonitoring() {
            try {
                await fetch('/api/stop_monitoring');
                document.getElementById('startBtn').disabled = false;
                document.getElementById('stopBtn').disabled = true;
                document.getElementById('status').textContent = '⏸️ Arrêté';
                document.getElementById('status').className = 'px-4 py-2 bg-gray-700 rounded-lg';
                
                if (updateInterval) {
                    clearInterval(updateInterval);
                    updateInterval = null;
                }
            } catch (error) {
                console.error('Erreur:', error);
            }
        }

        // Charger l'historique
        async function loadHistory() {
            try {
                const response = await fetch('/api/history');
                const history = await response.json();
                const tbody = document.getElementById('historyBody');
                
                if (history.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" class="text-center p-4 text-gray-500">Aucun signal enregistré</td></tr>';
                    return;
                }
                
                tbody.innerHTML = history.slice(-20).reverse().map(item => {
                    const time = new Date(item.timestamp).toLocaleTimeString('fr-FR');
                    const signalClass = item.signal === 'ACHAT' ? 'text-green-400' : 
                                      item.signal === 'VENTE' ? 'text-red-400' : 'text-gray-400';
                    const strength = (item.signal_details.strength * 100).toFixed(0);
                    return `
                        <tr class="border-b border-gray-700">
                            <td class="p-2">${time}</td>
                            <td class="p-2 ${signalClass} font-semibold">${item.signal}</td>
                            <td class="p-2">$${parseFloat(item.current_price).toLocaleString('fr-FR', {minimumFractionDigits: 2})}</td>
                            <td class="p-2">${item.indicators.rsi.toFixed(1)}</td>
                            <td class="p-2">${strength}%</td>
                        </tr>
                    `;
                }).join('');
            } catch (error) {
                console.error('Erreur:', error);
            }
        }

        // Initialiser les valeurs par défaut pour l'analyse avancée
        function initAdvancedAnalysis() {
            // Volatilité
            document.getElementById('volatilityRegime').textContent = 'Chargement...';
            document.getElementById('atr').textContent = '$0';
            document.getElementById('momentum').textContent = '0%';
            
            // Order Book
            document.getElementById('orderBookImbalance').textContent = '0%';
            document.getElementById('obSupports').textContent = '-';
            document.getElementById('obResistances').textContent = '-';
            
            // Niveaux clés
            document.getElementById('pivot').textContent = '$0';
            document.getElementById('r1').textContent = '$0';
            document.getElementById('s1').textContent = '$0';
            document.getElementById('techSupports').textContent = '-';
            document.getElementById('techResistances').textContent = '-';
            
            // Patterns
            document.getElementById('patternsList').textContent = 'Aucun pattern détecté';
            
            // Signaux de scalping
            document.getElementById('scalpingSignals').innerHTML = 
                '<div class="text-gray-300 text-sm">Chargement...</div>';
            document.getElementById('confidence').textContent = '-';
            
            // Suggestions de trades
            document.getElementById('tradesSuggestions').innerHTML = 
                '<div class="text-gray-300 text-sm">Chargement...</div>';
        }

        // Initialisation
        initChart();
        initAdvancedAnalysis();
        loadSignal();
        setInterval(loadHistory, 10000); // Mettre à jour l'historique toutes les 10 secondes
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    try:
        print("🚀 Démarrage du serveur web Hyperliquid...")
        print("📡 Accédez à http://localhost:5000 dans votre navigateur")
        init_generator()
        app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
    except Exception as e:
        print(f"Erreur: {e}")
        import traceback
        traceback.print_exc()

