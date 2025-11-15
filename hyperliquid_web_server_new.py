"""
Serveur web Flask pour monitoring des signaux Hyperliquid en temps réel
Version multi-coins avec affichage simultané
"""

import sys
import os

# Configuration de l'encodage UTF-8 pour Windows
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
supported_coins = getattr(config, 'SUPPORTED_COINS', ['BTC', 'ETH', 'SOL', 'HYPE', 'ARB'])

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hyperliquid Trading Signals - Multi-Coins</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1800px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            margin-bottom: 30px;
            font-size: 2em;
            color: #4ade80;
        }
        .coins-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .coin-card {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 20px;
            border: 2px solid rgba(255, 255, 255, 0.1);
            transition: all 0.3s;
        }
        .coin-card:hover {
            border-color: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
        }
        .coin-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        .coin-name {
            font-size: 1.5em;
            font-weight: bold;
        }
        .coin-price {
            font-size: 1.2em;
            color: #94a3b8;
        }
        .signal-badge {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: bold;
            margin-top: 10px;
        }
        .signal-buy {
            background: rgba(74, 222, 128, 0.2);
            color: #4ade80;
            border: 1px solid #4ade80;
        }
        .signal-sell {
            background: rgba(248, 113, 113, 0.2);
            color: #f87171;
            border: 1px solid #f87171;
        }
        .signal-neutral {
            background: rgba(148, 163, 184, 0.2);
            color: #94a3b8;
            border: 1px solid #94a3b8;
        }
        .signals-count {
            display: flex;
            gap: 15px;
            margin: 15px 0;
            font-size: 0.9em;
        }
        .signal-count-item {
            flex: 1;
            text-align: center;
            padding: 8px;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.05);
        }
        .signal-count-buy {
            color: #4ade80;
        }
        .signal-count-sell {
            color: #f87171;
        }
        .quality-indicator {
            width: 100%;
            height: 6px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 10px;
        }
        .quality-fill {
            height: 100%;
            background: linear-gradient(90deg, #f87171, #fbbf24, #4ade80);
            transition: width 0.3s ease;
        }
        .reasons-toggle {
            margin-top: 15px;
            padding: 8px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 6px;
            cursor: pointer;
            text-align: center;
            font-size: 0.85em;
            transition: all 0.3s;
        }
        .reasons-toggle:hover {
            background: rgba(255, 255, 255, 0.1);
        }
        .reasons-container {
            margin-top: 15px;
            display: none;
        }
        .reasons-container.show {
            display: block;
        }
        .reasons-group {
            margin-bottom: 15px;
        }
        .reasons-group-title {
            font-size: 0.9em;
            font-weight: bold;
            margin-bottom: 8px;
            padding: 6px 10px;
            border-radius: 6px;
        }
        .reasons-group-buy {
            background: rgba(74, 222, 128, 0.1);
            color: #4ade80;
        }
        .reasons-group-sell {
            background: rgba(248, 113, 113, 0.1);
            color: #f87171;
        }
        .reason-item {
            padding: 6px 10px;
            margin: 4px 0;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 4px;
            font-size: 0.8em;
            border-left: 3px solid;
        }
        .reason-item-buy {
            border-left-color: #4ade80;
        }
        .reason-item-sell {
            border-left-color: #f87171;
        }
        .timestamp {
            text-align: center;
            margin-top: 20px;
            opacity: 0.6;
            font-size: 0.85em;
        }
        .loading {
            text-align: center;
            padding: 20px;
            opacity: 0.7;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Hyperliquid Trading Signals - Multi-Coins</h1>
        
        <div class="coins-grid" id="coins-grid">
            <div class="loading">Chargement des signaux...</div>
        </div>
        
        <div class="timestamp" id="timestamp">-</div>
    </div>

    <script>
        let autoRefresh = true;
        let refreshInterval;
        let expandedCoins = {}; // {coin: true/false}

        function classifyReasons(reasons) {
            const buyReasons = [];
            const sellReasons = [];
            
            reasons.forEach(reason => {
                const reasonLower = reason.toLowerCase();
                if (reasonLower.includes('achat') || 
                    reasonLower.includes('buy') ||
                    reasonLower.includes('haussier') ||
                    reasonLower.includes('survendu') ||
                    reasonLower.includes('golden') ||
                    reasonLower.includes('au-dessus') ||
                    reasonLower.includes('support') ||
                    reasonLower.includes('rebond') ||
                    reasonLower.includes('positif')) {
                    buyReasons.push(reason);
                } else if (reasonLower.includes('vente') || 
                          reasonLower.includes('sell') ||
                          reasonLower.includes('baissier') ||
                          reasonLower.includes('suracheté') ||
                          reasonLower.includes('death') ||
                          reasonLower.includes('en-dessous') ||
                          reasonLower.includes('résistance') ||
                          reasonLower.includes('rejet') ||
                          reasonLower.includes('négatif')) {
                    sellReasons.push(reason);
                } else {
                    // Par défaut, classer selon le contexte
                    buyReasons.push(reason);
                }
            });
            
            return { buyReasons, sellReasons };
        }

        function createCoinCard(coin, data) {
            const signal = data.signal || 'NEUTRE';
            const quality = data.signal_quality || 0;
            const buySignals = data.buy_signals || 0;
            const sellSignals = data.sell_signals || 0;
            const reasons = data.reasons || [];
            const price = data.current_price || 0;
            
            const { buyReasons, sellReasons } = classifyReasons(reasons);
            const isExpanded = expandedCoins[coin] || false;
            
            const signalClass = signal === 'ACHAT' || signal === 'BUY' ? 'signal-buy' : 
                               signal === 'VENTE' || signal === 'SELL' ? 'signal-sell' : 'signal-neutral';
            
            return `
                <div class="coin-card">
                    <div class="coin-header">
                        <div>
                            <div class="coin-name">${coin}</div>
                            <div class="coin-price">$${price.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                        </div>
                        <div>
                            <div class="signal-badge ${signalClass}">${signal}</div>
                            <div style="font-size: 0.75em; margin-top: 5px; opacity: 0.7;">Qualité: ${quality.toFixed(0)}/100</div>
                        </div>
                    </div>
                    
                    <div class="signals-count">
                        <div class="signal-count-item signal-count-buy">
                            🟢 Achat: ${buySignals}
                        </div>
                        <div class="signal-count-item signal-count-sell">
                            🔴 Vente: ${sellSignals}
                        </div>
                    </div>
                    
                    <div class="quality-indicator">
                        <div class="quality-fill" style="width: ${quality}%"></div>
                    </div>
                    
                    ${reasons.length > 0 ? `
                        <div class="reasons-toggle" onclick="toggleReasons('${coin}')">
                            ${isExpanded ? '▼' : '▶'} Raisons (${reasons.length})
                        </div>
                        <div class="reasons-container ${isExpanded ? 'show' : ''}" id="reasons-${coin}">
                            ${buyReasons.length > 0 ? `
                                <div class="reasons-group">
                                    <div class="reasons-group-title reasons-group-buy">🟢 Signaux d'ACHAT (${buyReasons.length})</div>
                                    ${buyReasons.map(r => `<div class="reason-item reason-item-buy">${r}</div>`).join('')}
                                </div>
                            ` : ''}
                            ${sellReasons.length > 0 ? `
                                <div class="reasons-group">
                                    <div class="reasons-group-title reasons-group-sell">🔴 Signaux de VENTE (${sellReasons.length})</div>
                                    ${sellReasons.map(r => `<div class="reason-item reason-item-sell">${r}</div>`).join('')}
                                </div>
                            ` : ''}
                        </div>
                    ` : ''}
                </div>
            `;
        }

        function toggleReasons(coin) {
            expandedCoins[coin] = !expandedCoins[coin];
            const container = document.getElementById(`reasons-${coin}`);
            const toggle = container.previousElementSibling;
            if (container) {
                container.classList.toggle('show');
                toggle.textContent = `${expandedCoins[coin] ? '▼' : '▶'} Raisons`;
            }
        }

        function updateDisplay(allSignals) {
            const coinsGrid = document.getElementById('coins-grid');
            coinsGrid.innerHTML = '';
            
            const coins = Object.keys(allSignals).sort();
            
            if (coins.length === 0) {
                coinsGrid.innerHTML = '<div class="loading">Aucun signal disponible</div>';
                return;
            }
            
            coins.forEach(coin => {
                const coinCard = document.createElement('div');
                coinCard.innerHTML = createCoinCard(coin, allSignals[coin]);
                coinsGrid.appendChild(coinCard);
                
                // Réattacher les event listeners pour les raisons
                const toggleBtn = coinCard.querySelector('.reasons-toggle');
                if (toggleBtn) {
                    toggleBtn.onclick = () => toggleReasons(coin);
                }
            });
            
            document.getElementById('timestamp').textContent = 'Dernière mise à jour : ' + new Date().toLocaleString('fr-FR');
        }

        function refreshAllSignals() {
            fetch('/api/signals/all')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error(data.error);
                    } else {
                        updateDisplay(data.signals);
                    }
                })
                .catch(error => {
                    console.error('Erreur:', error);
                });
        }

        function toggleAutoRefresh() {
            autoRefresh = !autoRefresh;
            if (autoRefresh) {
                refreshInterval = setInterval(refreshAllSignals, 5000);
            } else {
                clearInterval(refreshInterval);
            }
        }

        // Initialisation
        refreshAllSignals();
        if (autoRefresh) {
            refreshInterval = setInterval(refreshAllSignals, 5000);
        }
    </script>
</body>
</html>
"""

def init_all_generators():
    """Initialise les générateurs pour tous les coins"""
    global signal_generators
    
    for coin in supported_coins:
        try:
            generator = HyperliquidSignalGenerator(
                coin=coin,
                interval=config.DEFAULT_INTERVAL
            )
            candles = generator.fetch_historical_candles(limit=200)
            if candles:
                generator.candles = candles
                signal_generators[coin] = generator
                logger.info(f"✅ Générateur initialisé: {coin} - {len(candles)} chandeliers")
            else:
                logger.warning(f"⚠️  Aucun chandelier pour {coin}")
        except Exception as e:
            logger.error(f"❌ Erreur initialisation {coin}: {e}")

def monitor_signals():
    """Thread de monitoring des signaux pour tous les coins"""
    global current_signals, last_update, monitoring_active
    
    while monitoring_active:
        try:
            for coin, generator in signal_generators.items():
                try:
                    analysis = generator.analyze()
                    
                    if 'error' not in analysis:
                        signal_details = analysis.get('signal_details', {})
                        current_signals[coin] = {
                            'signal': analysis.get('signal', 'NEUTRE'),
                            'signal_quality': analysis.get('signal_quality', 0),
                            'current_price': analysis.get('current_price', 0),
                            'coin': coin,
                            'indicators': analysis.get('indicators', {}),
                            'volume_ratio': analysis.get('volume_ratio', 0),
                            'signal_details': signal_details,
                            'buy_signals': signal_details.get('buy_signals', 0),
                            'sell_signals': signal_details.get('sell_signals', 0),
                            'reasons': signal_details.get('reasons', []),
                            'timestamp': datetime.now().isoformat()
                        }
                except Exception as e:
                    logger.error(f"Erreur analyse {coin}: {e}")
            
            last_update = datetime.now()
            time.sleep(config.WEB_UPDATE_INTERVAL)
            
        except Exception as e:
            logger.error(f"Erreur monitoring: {e}", exc_info=True)
            time.sleep(5)

@app.route('/')
def index():
    """Page principale"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/signals/all')
def get_all_signals():
    """API pour récupérer tous les signaux"""
    global current_signals
    
    # Si pas de signaux en cache, générer immédiatement
    if not current_signals:
        for coin, generator in signal_generators.items():
            try:
                if not generator.candles or len(generator.candles) < 50:
                    candles = generator.fetch_historical_candles(limit=200)
                    if candles:
                        generator.candles = candles
                
                analysis = generator.analyze()
                if 'error' not in analysis:
                    signal_details = analysis.get('signal_details', {})
                    current_signals[coin] = {
                        'signal': analysis.get('signal', 'NEUTRE'),
                        'signal_quality': analysis.get('signal_quality', 0),
                        'current_price': analysis.get('current_price', 0),
                        'coin': coin,
                        'indicators': analysis.get('indicators', {}),
                        'volume_ratio': analysis.get('volume_ratio', 0),
                        'signal_details': signal_details,
                        'buy_signals': signal_details.get('buy_signals', 0),
                        'sell_signals': signal_details.get('sell_signals', 0),
                        'reasons': signal_details.get('reasons', []),
                        'timestamp': datetime.now().isoformat()
                    }
            except Exception as e:
                logger.error(f"Erreur génération signal {coin}: {e}")
                current_signals[coin] = {
                    'signal': 'NEUTRE',
                    'signal_quality': 0,
                    'current_price': 0,
                    'coin': coin,
                    'error': str(e)
                }
    
    return jsonify({
        'signals': current_signals,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/status')
def get_status():
    """API pour le statut du système"""
    return jsonify({
        'monitoring_active': monitoring_active,
        'last_update': last_update.isoformat() if last_update else None,
        'supported_coins': supported_coins,
        'active_coins': list(signal_generators.keys())
    })

if __name__ == '__main__':
    logger.info("🚀 Démarrage du serveur web Hyperliquid Multi-Coins...")
    logger.info(f"📊 Coins supportés: {', '.join(supported_coins)}")
    
    init_all_generators()
    
    if not signal_generators:
        logger.error("❌ Aucun générateur initialisé")
        sys.exit(1)
    
    # Démarrer le monitoring en arrière-plan
    monitoring_active = True
    monitoring_thread = threading.Thread(target=monitor_signals, daemon=True)
    monitoring_thread.start()
    
    logger.info(f"✅ Serveur démarré sur http://{config.WEB_SERVER_HOST}:{config.WEB_SERVER_PORT}")
    logger.info(f"📊 Monitoring: {len(signal_generators)} coins")
    
    try:
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

