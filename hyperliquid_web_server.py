"""
Serveur web Flask pour monitoring des signaux Hyperliquid en temps réel
Optimisé pour scalping haute fréquence
"""

import sys
import os

# Configuration de l'encodage UTF-8 pour Windows (sans modifier sys.stdout directement)
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
import threading
import time
import logging
from datetime import datetime
from hyperliquid_signals import HyperliquidSignalGenerator
import config

# Configuration du logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# État global
signal_generator = None
current_signal = None
last_update = None
monitoring_active = False
monitoring_thread = None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hyperliquid Trading Signals - Monitoring</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .status-card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        }
        .signal-display {
            font-size: 3em;
            text-align: center;
            margin: 20px 0;
            font-weight: bold;
            text-shadow: 3px 3px 6px rgba(0,0,0,0.5);
        }
        .signal-buy { color: #4ade80; }
        .signal-sell { color: #f87171; }
        .signal-neutral { color: #94a3b8; }
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        .info-item {
            background: rgba(255, 255, 255, 0.05);
            padding: 15px;
            border-radius: 10px;
            border-left: 4px solid #667eea;
        }
        .info-label {
            font-size: 0.9em;
            opacity: 0.8;
            margin-bottom: 5px;
        }
        .info-value {
            font-size: 1.3em;
            font-weight: bold;
        }
        .quality-bar {
            width: 100%;
            height: 30px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            overflow: hidden;
            margin-top: 10px;
        }
        .quality-fill {
            height: 100%;
            background: linear-gradient(90deg, #f87171, #fbbf24, #4ade80);
            transition: width 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #000;
            font-weight: bold;
        }
        .timestamp {
            text-align: center;
            margin-top: 20px;
            opacity: 0.7;
            font-size: 0.9em;
        }
        .controls {
            display: flex;
            gap: 10px;
            justify-content: center;
            margin-top: 20px;
        }
        button {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 1em;
            cursor: pointer;
            background: rgba(255, 255, 255, 0.2);
            color: #fff;
            transition: all 0.3s;
        }
        button:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
        }
        .loading {
            text-align: center;
            margin: 40px 0;
            font-size: 1.2em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Hyperliquid Trading Signals</h1>
        
        <div class="status-card">
            <div id="signal-display" class="signal-display signal-neutral">
                Chargement...
            </div>
            
            <div class="info-grid" id="info-grid">
                <div class="info-item">
                    <div class="info-label">Coin</div>
                    <div class="info-value" id="coin">-</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Prix Actuel</div>
                    <div class="info-value" id="price">-</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Qualité Signal</div>
                    <div class="info-value" id="quality">-</div>
                    <div class="quality-bar">
                        <div class="quality-fill" id="quality-fill" style="width: 0%">0%</div>
                    </div>
                </div>
                <div class="info-item">
                    <div class="info-label">RSI</div>
                    <div class="info-value" id="rsi">-</div>
                </div>
                <div class="info-item">
                    <div class="info-label">MACD</div>
                    <div class="info-value" id="macd">-</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Volume Ratio</div>
                    <div class="info-value" id="volume">-</div>
                </div>
            </div>
            
            <div class="timestamp" id="timestamp">-</div>
            
            <div class="controls">
                <button onclick="refreshSignal()">🔄 Actualiser</button>
                <button onclick="toggleAutoRefresh()">⏸️ Auto-refresh</button>
            </div>
        </div>
    </div>

    <script>
        let autoRefresh = true;
        let refreshInterval;

        function updateDisplay(data) {
            const signal = data.signal || 'NEUTRE';
            const quality = data.signal_quality || 0;
            
            const display = document.getElementById('signal-display');
            display.textContent = signal;
            display.className = 'signal-display ' + 
                (signal === 'ACHAT' || signal === 'BUY' ? 'signal-buy' : 
                 signal === 'VENTE' || signal === 'SELL' ? 'signal-sell' : 'signal-neutral');
            
            document.getElementById('coin').textContent = data.coin || '-';
            document.getElementById('price').textContent = data.current_price ? '$' + parseFloat(data.current_price).toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '-';
            document.getElementById('quality').textContent = quality.toFixed(1) + '/100';
            document.getElementById('quality-fill').style.width = quality + '%';
            document.getElementById('quality-fill').textContent = quality.toFixed(0) + '%';
            
            const indicators = data.indicators || {};
            document.getElementById('rsi').textContent = indicators.rsi ? indicators.rsi.toFixed(1) : '-';
            document.getElementById('macd').textContent = indicators.macd ? indicators.macd.histogram.toFixed(4) : '-';
            document.getElementById('volume').textContent = data.volume_ratio ? data.volume_ratio.toFixed(2) + 'x' : '-';
            
            document.getElementById('timestamp').textContent = 'Dernière mise à jour : ' + new Date().toLocaleString('fr-FR');
        }

        function refreshSignal() {
            fetch('/api/signal')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('signal-display').textContent = 'Erreur';
                        console.error(data.error);
                    } else {
                        updateDisplay(data);
                    }
                })
                .catch(error => {
                    console.error('Erreur:', error);
                    document.getElementById('signal-display').textContent = 'Erreur';
                });
        }

        function toggleAutoRefresh() {
            autoRefresh = !autoRefresh;
            if (autoRefresh) {
                refreshInterval = setInterval(refreshSignal, 5000);
                document.querySelector('button[onclick="toggleAutoRefresh()"]').textContent = '⏸️ Auto-refresh';
            } else {
                clearInterval(refreshInterval);
                document.querySelector('button[onclick="toggleAutoRefresh()"]').textContent = '▶️ Auto-refresh';
            }
        }

        // Initialisation
        refreshSignal();
        if (autoRefresh) {
            refreshInterval = setInterval(refreshSignal, 5000);
        }
    </script>
</body>
</html>
"""

def init_generator():
    """Initialise le générateur de signaux"""
    global signal_generator
    try:
        signal_generator = HyperliquidSignalGenerator(
            coin=config.DEFAULT_COIN,
            interval=config.DEFAULT_INTERVAL
        )
        # Charger les données historiques nécessaires pour l'analyse
        logger.info(f"📥 Chargement des données historiques pour {config.DEFAULT_COIN}...")
        candles = signal_generator.fetch_historical_candles(limit=200)
        if candles:
            signal_generator.candles = candles
            logger.info(f"✅ Générateur initialisé: {config.DEFAULT_COIN} ({config.DEFAULT_INTERVAL}) - {len(candles)} chandeliers")
        else:
            logger.warning(f"⚠️  Aucun chandelier récupéré, le générateur utilisera les données en temps réel")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur initialisation: {e}", exc_info=True)
        return False

def monitor_signals():
    """Thread de monitoring des signaux"""
    global current_signal, last_update, monitoring_active
    
    while monitoring_active:
        try:
            if signal_generator:
                analysis = signal_generator.analyze()
                
                if 'error' not in analysis:
                    current_signal = {
                        'signal': analysis.get('signal', 'NEUTRE'),
                        'signal_quality': analysis.get('signal_quality', 0),
                        'current_price': analysis.get('current_price', 0),
                        'coin': signal_generator.coin,
                        'indicators': analysis.get('indicators', {}),
                        'volume_ratio': analysis.get('volume_ratio', 0),
                        'timestamp': datetime.now().isoformat()
                    }
                    last_update = datetime.now()
                else:
                    logger.warning(f"Erreur analyse: {analysis.get('error')}")
            
            time.sleep(config.WEB_UPDATE_INTERVAL)
            
        except Exception as e:
            logger.error(f"Erreur monitoring: {e}", exc_info=True)
            time.sleep(5)

@app.route('/')
def index():
    """Page principale"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/signal')
def get_signal():
    """API pour récupérer le signal actuel"""
    global current_signal
    
    if not signal_generator:
        return jsonify({'error': 'Générateur non initialisé', 'signal': 'NEUTRE'}), 200
    
    # Toujours générer un signal à la demande (plus fiable)
    try:
        # S'assurer qu'on a des données historiques
        if not signal_generator.candles or len(signal_generator.candles) < 50:
            candles = signal_generator.fetch_historical_candles(limit=200)
            if candles:
                signal_generator.candles = candles
        
        analysis = signal_generator.analyze()
        if 'error' not in analysis:
            current_signal = {
                'signal': analysis.get('signal', 'NEUTRE'),
                'signal_quality': analysis.get('signal_quality', 0),
                'current_price': analysis.get('current_price', 0),
                'coin': signal_generator.coin,
                'indicators': analysis.get('indicators', {}),
                'volume_ratio': analysis.get('volume_ratio', 0),
                'timestamp': datetime.now().isoformat()
            }
            return jsonify(current_signal)
        else:
            # Retourner un signal NEUTRE en cas d'erreur plutôt qu'une erreur 500
            return jsonify({
                'signal': 'NEUTRE',
                'signal_quality': 0,
                'current_price': 0,
                'coin': signal_generator.coin,
                'error': analysis.get('error'),
                'timestamp': datetime.now().isoformat()
            }), 200
    except Exception as e:
        logger.error(f"Erreur génération signal: {e}", exc_info=True)
        return jsonify({
            'signal': 'NEUTRE',
            'signal_quality': 0,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 200

@app.route('/api/status')
def get_status():
    """API pour le statut du système"""
    return jsonify({
        'monitoring_active': monitoring_active,
        'last_update': last_update.isoformat() if last_update else None,
        'coin': signal_generator.coin if signal_generator else None,
        'interval': signal_generator.interval if signal_generator else None
    })

if __name__ == '__main__':
    logger.info("🚀 Démarrage du serveur web Hyperliquid...")
    
    if not init_generator():
        logger.error("❌ Impossible d'initialiser le générateur")
        sys.exit(1)
    
    # Démarrer le monitoring en arrière-plan
    monitoring_active = True
    monitoring_thread = threading.Thread(target=monitor_signals, daemon=True)
    monitoring_thread.start()
    
    logger.info(f"✅ Serveur démarré sur http://{config.WEB_SERVER_HOST}:{config.WEB_SERVER_PORT}")
    logger.info(f"📊 Monitoring: {config.DEFAULT_COIN} ({config.DEFAULT_INTERVAL})")
    
    try:
        # Désactiver le banner Flask pour éviter les problèmes d'encodage Windows
        import os
        os.environ['FLASK_ENV'] = 'production'
        
        app.run(
            host=config.WEB_SERVER_HOST,
            port=config.WEB_SERVER_PORT,
            debug=False,
            threaded=True,
            use_reloader=False
        )
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt du serveur...")
        monitoring_active = False
        if monitoring_thread:
            monitoring_thread.join(timeout=2)
