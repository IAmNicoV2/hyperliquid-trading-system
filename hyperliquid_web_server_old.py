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
signal_generators = {}  # {coin: generator}
current_signals = {}  # {coin: signal_data}
last_update = None
monitoring_active = False
monitoring_thread = None
supported_coins = getattr(config, 'SUPPORTED_COINS', ['BTC'])

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
            max-width: 1400px;
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
            padding: 20px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.05);
        }
        .signal-buy { color: #4ade80; border: 3px solid #4ade80; }
        .signal-sell { color: #f87171; border: 3px solid #f87171; }
        .signal-neutral { color: #94a3b8; border: 3px solid #94a3b8; }
        
        /* NOUVEAU: Visuel des signaux */
        .signals-visual {
            margin: 30px 0;
            padding: 25px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
        }
        .signals-header {
            text-align: center;
            font-size: 1.3em;
            margin-bottom: 20px;
            font-weight: bold;
        }
        .signals-balance {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 20px;
            margin-bottom: 25px;
        }
        .signal-counter {
            flex: 1;
            text-align: center;
            padding: 20px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.05);
            transition: all 0.3s;
        }
        .signal-counter.buy {
            border: 2px solid #4ade80;
            box-shadow: 0 0 20px rgba(74, 222, 128, 0.3);
        }
        .signal-counter.sell {
            border: 2px solid #f87171;
            box-shadow: 0 0 20px rgba(248, 113, 113, 0.3);
        }
        .signal-counter-label {
            font-size: 0.9em;
            opacity: 0.8;
            margin-bottom: 10px;
        }
        .signal-counter-value {
            font-size: 3em;
            font-weight: bold;
            margin: 10px 0;
        }
        .signal-counter.buy .signal-counter-value { color: #4ade80; }
        .signal-counter.sell .signal-counter-value { color: #f87171; }
        
        .signals-impact-bar {
            width: 100%;
            height: 50px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 25px;
            overflow: hidden;
            position: relative;
            margin: 20px 0;
        }
        .impact-buy {
            height: 100%;
            background: linear-gradient(90deg, #4ade80, #22c55e);
            float: left;
            transition: width 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #000;
            font-weight: bold;
            font-size: 1.2em;
        }
        .impact-sell {
            height: 100%;
            background: linear-gradient(90deg, #f87171, #ef4444);
            float: right;
            transition: width 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
            font-weight: bold;
            font-size: 1.2em;
        }
        .impact-neutral {
            height: 100%;
            background: rgba(148, 163, 184, 0.5);
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
            font-weight: bold;
            font-size: 1.2em;
        }
        
        .reasons-section {
            margin-top: 30px;
        }
        .reasons-title {
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 15px;
            text-align: center;
        }
        .reasons-list {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 10px;
        }
        .reason-item {
            padding: 12px 15px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            border-left: 4px solid;
            font-size: 0.9em;
            transition: all 0.3s;
        }
        .reason-item.buy-reason {
            border-left-color: #4ade80;
        }
        .reason-item.sell-reason {
            border-left-color: #f87171;
        }
        .reason-item:hover {
            background: rgba(255, 255, 255, 0.1);
            transform: translateX(5px);
        }
        
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
            
            <!-- NOUVEAU: Visuel des signaux -->
            <div class="signals-visual">
                <div class="signals-header">📊 Impact des Signaux sur la Décision</div>
                
                <div class="signals-balance">
                    <div class="signal-counter buy" id="buy-counter">
                        <div class="signal-counter-label">🟢 Signaux d'ACHAT</div>
                        <div class="signal-counter-value" id="buy-signals">0</div>
                    </div>
                    <div class="signal-counter sell" id="sell-counter">
                        <div class="signal-counter-label">🔴 Signaux de VENTE</div>
                        <div class="signal-counter-value" id="sell-signals">0</div>
                    </div>
                </div>
                
                <div class="signals-impact-bar" id="impact-bar">
                    <div class="impact-neutral">NEUTRE</div>
                </div>
                
                <div class="reasons-section" id="reasons-section" style="display: none;">
                    <div class="reasons-title">📋 Raisons des Signaux</div>
                    <div class="reasons-list" id="reasons-list"></div>
                </div>
            </div>
            
            <!-- Sélecteur de coin -->
            <div class="coin-selector" style="margin: 20px 0; text-align: center;">
                <label for="coin-select" style="margin-right: 10px; font-weight: bold;">Coin:</label>
                <select id="coin-select" style="padding: 8px 15px; border-radius: 8px; background: rgba(255, 255, 255, 0.1); color: #fff; border: 2px solid rgba(255, 255, 255, 0.3); font-size: 1em; cursor: pointer;" onchange="changeCoin(this.value)">
                    <option value="BTC">BTC</option>
                    <option value="ETH">ETH</option>
                    <option value="SOL">SOL</option>
                    <option value="HYPE">HYPE</option>
                    <option value="ARB">ARB</option>
                </select>
                <button onclick="refreshCoinList()" style="margin-left: 10px; padding: 8px 15px; border-radius: 8px; background: rgba(255, 255, 255, 0.2); color: #fff; border: none; cursor: pointer;">🔄</button>
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

        function updateSignalsVisual(buySignals, sellSignals, reasons) {
            // Mettre à jour les compteurs
            document.getElementById('buy-signals').textContent = buySignals;
            document.getElementById('sell-signals').textContent = sellSignals;
            
            // Calculer le pourcentage pour la barre d'impact
            const total = buySignals + sellSignals;
            let buyPercent = 0;
            let sellPercent = 0;
            
            if (total > 0) {
                buyPercent = (buySignals / total) * 100;
                sellPercent = (sellSignals / total) * 100;
            }
            
            // Mettre à jour la barre d'impact
            const impactBar = document.getElementById('impact-bar');
            impactBar.innerHTML = '';
            
            if (buySignals > sellSignals) {
                impactBar.innerHTML = `
                    <div class="impact-buy" style="width: ${buyPercent}%">
                        ACHAT ${buyPercent.toFixed(0)}%
                    </div>
                `;
            } else if (sellSignals > buySignals) {
                impactBar.innerHTML = `
                    <div class="impact-sell" style="width: ${sellPercent}%">
                        VENTE ${sellPercent.toFixed(0)}%
                    </div>
                `;
            } else {
                impactBar.innerHTML = '<div class="impact-neutral">NEUTRE</div>';
            }
            
            // Mettre à jour les raisons
            const reasonsSection = document.getElementById('reasons-section');
            const reasonsList = document.getElementById('reasons-list');
            
            if (reasons && reasons.length > 0) {
                reasonsSection.style.display = 'block';
                reasonsList.innerHTML = '';
                
                reasons.forEach(reason => {
                    const reasonItem = document.createElement('div');
                    reasonItem.className = 'reason-item';
                    
                    // Déterminer si c'est une raison d'achat ou de vente
                    if (reason.toLowerCase().includes('achat') || 
                        reason.toLowerCase().includes('buy') ||
                        reason.toLowerCase().includes('haussier') ||
                        reason.toLowerCase().includes('survendu') ||
                        reason.toLowerCase().includes('golden') ||
                        reason.toLowerCase().includes('au-dessus')) {
                        reasonItem.classList.add('buy-reason');
                    } else if (reason.toLowerCase().includes('vente') || 
                               reason.toLowerCase().includes('sell') ||
                               reason.toLowerCase().includes('baissier') ||
                               reason.toLowerCase().includes('suracheté') ||
                               reason.toLowerCase().includes('death') ||
                               reason.toLowerCase().includes('en-dessous')) {
                        reasonItem.classList.add('sell-reason');
                    }
                    
                    reasonItem.textContent = reason;
                    reasonsList.appendChild(reasonItem);
                });
            } else {
                reasonsSection.style.display = 'none';
            }
        }

        function updateDisplay(data) {
            const signal = data.signal || 'NEUTRE';
            const quality = data.signal_quality || 0;
            const buySignals = data.buy_signals || 0;
            const sellSignals = data.sell_signals || 0;
            const reasons = data.reasons || [];
            
            // Mettre à jour le signal principal
            const display = document.getElementById('signal-display');
            display.textContent = signal;
            display.className = 'signal-display ' + 
                (signal === 'ACHAT' || signal === 'BUY' ? 'signal-buy' : 
                 signal === 'VENTE' || signal === 'SELL' ? 'signal-sell' : 'signal-neutral');
            
            // Mettre à jour le visuel des signaux
            updateSignalsVisual(buySignals, sellSignals, reasons);
            
            // Mettre à jour les autres informations
            const coin = data.coin || '-';
            document.getElementById('coin').textContent = coin;
            
            // Mettre à jour le sélecteur de coin
            const coinSelect = document.getElementById('coin-select');
            if (coinSelect && coin !== '-') {
                coinSelect.value = coin;
            }
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

        // Fonction pour changer de coin
        function changeCoin(coin) {
            fetch(`/api/coin/${coin}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log(`Coin changé vers ${coin}`);
                    refreshSignal(); // Rafraîchir immédiatement
                } else {
                    alert('Erreur: ' + (data.error || 'Impossible de changer de coin'));
                }
            })
            .catch(error => {
                console.error('Erreur changement de coin:', error);
                alert('Erreur lors du changement de coin');
            });
        }

        // Fonction pour rafraîchir la liste des coins
        function refreshCoinList() {
            fetch('/api/coins')
                .then(response => response.json())
                .then(data => {
                    const select = document.getElementById('coin-select');
                    select.innerHTML = '';
                    data.supported_coins.forEach(coin => {
                        const option = document.createElement('option');
                        option.value = coin;
                        option.textContent = coin;
                        if (coin === data.current_coin) {
                            option.selected = true;
                        }
                        select.appendChild(option);
                    });
                })
                .catch(error => {
                    console.error('Erreur rafraîchissement liste coins:', error);
                });
        }

        // Initialisation
        refreshCoinList();
        refreshSignal();
        if (autoRefresh) {
            refreshInterval = setInterval(refreshSignal, 5000);
        }
    </script>
</body>
</html>
"""

def init_generator(coin=None):
    """Initialise le générateur de signaux"""
    global signal_generator, current_coin
    try:
        coin = coin or config.DEFAULT_COIN
        current_coin = coin
        signal_generator = HyperliquidSignalGenerator(
            coin=coin,
            interval=config.DEFAULT_INTERVAL
        )
        # Charger les données historiques nécessaires pour l'analyse
        logger.info(f"📥 Chargement des données historiques pour {coin}...")
        candles = signal_generator.fetch_historical_candles(limit=200)
        if candles:
            signal_generator.candles = candles
            logger.info(f"✅ Générateur initialisé: {coin} ({config.DEFAULT_INTERVAL}) - {len(candles)} chandeliers")
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
                    signal_details = analysis.get('signal_details', {})
                    current_signal = {
                        'signal': analysis.get('signal', 'NEUTRE'),
                        'signal_quality': analysis.get('signal_quality', 0),
                        'current_price': analysis.get('current_price', 0),
                        'coin': signal_generator.coin,
                        'indicators': analysis.get('indicators', {}),
                        'volume_ratio': analysis.get('volume_ratio', 0),
                        'signal_details': signal_details,
                        'buy_signals': signal_details.get('buy_signals', 0),
                        'sell_signals': signal_details.get('sell_signals', 0),
                        'reasons': signal_details.get('reasons', []),
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
            signal_details = analysis.get('signal_details', {})
            # Debug: vérifier si signal_details est présent
            if not signal_details:
                logger.warning(f"signal_details manquant dans analysis. Keys: {list(analysis.keys())}")
            
            current_signal = {
                'signal': analysis.get('signal', 'NEUTRE'),
                'signal_quality': analysis.get('signal_quality', 0),
                'current_price': analysis.get('current_price', 0),
                'coin': signal_generator.coin,
                'indicators': analysis.get('indicators', {}),
                'volume_ratio': analysis.get('volume_ratio', 0),
                'signal_details': signal_details,
                'buy_signals': signal_details.get('buy_signals', 0) if signal_details else 0,
                'sell_signals': signal_details.get('sell_signals', 0) if signal_details else 0,
                'reasons': signal_details.get('reasons', []) if signal_details else [],
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
        'interval': signal_generator.interval if signal_generator else None,
        'supported_coins': getattr(config, 'SUPPORTED_COINS', ['BTC'])
    })

@app.route('/api/coins')
def get_coins():
    """API pour récupérer la liste des coins supportés"""
    return jsonify({
        'supported_coins': getattr(config, 'SUPPORTED_COINS', ['BTC']),
        'current_coin': current_coin or config.DEFAULT_COIN
    })

@app.route('/api/coin/<coin>', methods=['POST'])
def set_coin(coin):
    """API pour changer le coin surveillé"""
    global signal_generator, current_coin
    
    supported_coins = getattr(config, 'SUPPORTED_COINS', ['BTC'])
    if coin.upper() not in supported_coins:
        return jsonify({
            'error': f'Coin non supporté. Coins disponibles: {", ".join(supported_coins)}',
            'supported_coins': supported_coins
        }), 400
    
    coin = coin.upper()
    
    try:
        # Réinitialiser le générateur avec le nouveau coin
        if init_generator(coin):
            current_coin = coin
            logger.info(f"🔄 Coin changé vers {coin}")
            return jsonify({
                'success': True,
                'coin': coin,
                'message': f'Coin changé vers {coin}'
            })
        else:
            return jsonify({
                'error': f'Impossible d\'initialiser le générateur pour {coin}'
            }), 500
    except Exception as e:
        logger.error(f"Erreur changement de coin: {e}", exc_info=True)
        return jsonify({
            'error': str(e)
        }), 500

if __name__ == '__main__':
    logger.info("🚀 Démarrage du serveur web Hyperliquid...")
    
    supported_coins = getattr(config, 'SUPPORTED_COINS', ['BTC'])
    logger.info(f"📊 Coins supportés: {', '.join(supported_coins)}")
    
    if not init_generator():
        logger.error("❌ Impossible d'initialiser le générateur")
        sys.exit(1)
    
    # Démarrer le monitoring en arrière-plan
    monitoring_active = True
    monitoring_thread = threading.Thread(target=monitor_signals, daemon=True)
    monitoring_thread.start()
    
    logger.info(f"✅ Serveur démarré sur http://{config.WEB_SERVER_HOST}:{config.WEB_SERVER_PORT}")
    logger.info(f"📊 Monitoring: {current_coin or config.DEFAULT_COIN} ({config.DEFAULT_INTERVAL})")
    
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
