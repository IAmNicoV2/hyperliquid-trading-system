"""
Serveur web Flask pour monitoring des signaux Hyperliquid en temps réel
Version multi-coins avec affichage simultané
"""

import sys
import os

# Configuration de l'encodage UTF-8 pour Windows
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS
import threading
import time
import logging
from datetime import datetime
from hyperliquid_signals import HyperliquidSignalGenerator
from trading_decision import TradingDecisionEngine
from order_manager import OrderManager, OrderStatus
from performance_analyzer import PerformanceAnalyzer
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

# Système de décision de trading
decision_engine = TradingDecisionEngine()
order_manager = OrderManager()
performance_analyzer = PerformanceAnalyzer(order_manager)
current_positions = {}  # {coin: position_info}

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
        
        /* Section Ordres */
        .orders-section {
            margin-top: 40px;
            padding: 25px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
        }
        .orders-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .orders-title {
            font-size: 1.5em;
            font-weight: bold;
        }
        .stats-summary {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }
        .stat-item {
            padding: 10px 15px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            text-align: center;
        }
        .stat-label {
            font-size: 0.8em;
            opacity: 0.7;
            margin-bottom: 5px;
        }
        .stat-value {
            font-size: 1.3em;
            font-weight: bold;
        }
        .stat-value.positive { color: #4ade80; }
        .stat-value.negative { color: #f87171; }
        
        .orders-tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid rgba(255, 255, 255, 0.1);
        }
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.3s;
            opacity: 0.6;
        }
        .tab.active {
            opacity: 1;
            border-bottom-color: #4ade80;
        }
        .tab:hover {
            opacity: 1;
        }
        
        .orders-list {
            display: grid;
            gap: 15px;
        }
        .order-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            padding: 15px;
            border-left: 4px solid;
            transition: all 0.3s;
        }
        .order-card:hover {
            background: rgba(255, 255, 255, 0.08);
            transform: translateX(5px);
        }
        .order-card.pending { border-left-color: #fbbf24; }
        .order-card.accepted { border-left-color: #3b82f6; }
        .order-card.executed { border-left-color: #8b5cf6; }
        .order-card.closed { border-left-color: #94a3b8; }
        .order-card.rejected { border-left-color: #f87171; }
        
        .order-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 10px;
        }
        .order-info {
            flex: 1;
        }
        .order-coin {
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .order-signal {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: bold;
            margin-right: 10px;
        }
        .order-signal.buy { background: rgba(74, 222, 128, 0.2); color: #4ade80; }
        .order-signal.sell { background: rgba(248, 113, 113, 0.2); color: #f87171; }
        .order-status {
            padding: 6px 12px;
            border-radius: 15px;
            font-size: 0.8em;
            font-weight: bold;
        }
        .order-status.pending { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }
        .order-status.accepted { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
        .order-status.executed { background: rgba(139, 92, 246, 0.2); color: #8b5cf6; }
        .order-status.closed { background: rgba(148, 163, 184, 0.2); color: #94a3b8; }
        .order-status.rejected { background: rgba(248, 113, 113, 0.2); color: #f87171; }
        
        .order-details {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            margin-top: 10px;
            font-size: 0.85em;
        }
        .order-detail-item {
            padding: 8px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 6px;
        }
        .order-detail-label {
            opacity: 0.7;
            font-size: 0.9em;
            margin-bottom: 3px;
        }
        .order-detail-value {
            font-weight: bold;
        }
        .order-actions {
            display: flex;
            gap: 8px;
            margin-top: 10px;
        }
        .order-btn {
            padding: 6px 12px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85em;
            transition: all 0.3s;
        }
        .order-btn.accept {
            background: rgba(74, 222, 128, 0.2);
            color: #4ade80;
            border: 1px solid #4ade80;
        }
        .order-btn.accept:hover {
            background: rgba(74, 222, 128, 0.3);
        }
        .order-btn.reject {
            background: rgba(248, 113, 113, 0.2);
            color: #f87171;
            border: 1px solid #f87171;
        }
        .order-btn.reject:hover {
            background: rgba(248, 113, 113, 0.3);
        }
        .order-btn.execute {
            background: rgba(139, 92, 246, 0.2);
            color: #8b5cf6;
            border: 1px solid #8b5cf6;
        }
        .order-btn.execute:hover {
            background: rgba(139, 92, 246, 0.3);
        }
        .pnl-positive { color: #4ade80; }
        .pnl-negative { color: #f87171; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Hyperliquid Trading Signals - Multi-Coins</h1>
        
        <div class="coins-grid" id="coins-grid">
            <div class="loading">Chargement des signaux...</div>
        </div>

        <!-- Section Ordres -->
        <div class="orders-section">
            <div class="orders-header">
                <div class="orders-title">📋 Ordres de Trading</div>
                <div class="stats-summary" id="stats-summary">
                    <div class="stat-item">
                        <div class="stat-label">Winrate</div>
                        <div class="stat-value" id="stat-winrate">-</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Profit Factor</div>
                        <div class="stat-value" id="stat-profit-factor">-</div>
                </div>
                    <div class="stat-item">
                        <div class="stat-label">Total Trades</div>
                        <div class="stat-value" id="stat-total-trades">-</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">P&L Total</div>
                        <div class="stat-value" id="stat-total-pnl">-</div>
                </div>
            </div>
        </div>

            <div class="orders-tabs">
                <div class="tab active" onclick="showOrdersTab('pending')">⏳ En Attente (<span id="count-pending">0</span>)</div>
                <div class="tab" onclick="showOrdersTab('accepted')">✅ Acceptés (<span id="count-accepted">0</span>)</div>
                <div class="tab" onclick="showOrdersTab('executed')">🚀 Exécutés (<span id="count-executed">0</span>)</div>
                <div class="tab" onclick="showOrdersTab('closed')">🔒 Fermés (<span id="count-closed">0</span>)</div>
        </div>

            <div class="orders-list" id="orders-list">
                <div class="loading">Chargement des ordres...</div>
            </div>
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
            console.log('updateDisplay appelé avec:', allSignals);
            const coinsGrid = document.getElementById('coins-grid');
            if (!coinsGrid) {
                console.error('Element coins-grid non trouvé!');
                    return;
                }
                
            coinsGrid.innerHTML = '';
            
            const coins = Object.keys(allSignals || {}).sort();
            console.log('Coins à afficher:', coins);
            
            if (coins.length === 0) {
                coinsGrid.innerHTML = '<div class="loading">Aucun signal disponible</div>';
                return;
            }
            
            coins.forEach(coin => {
                try {
                    const coinData = allSignals[coin];
                    if (!coinData) {
                        console.warn('Pas de données pour', coin);
                        return;
                    }
                    const coinCard = document.createElement('div');
                    coinCard.innerHTML = createCoinCard(coin, coinData);
                    coinsGrid.appendChild(coinCard);
                    
                    // Réattacher les event listeners pour les raisons
                    const toggleBtn = coinCard.querySelector('.reasons-toggle');
                    if (toggleBtn) {
                        toggleBtn.onclick = () => toggleReasons(coin);
                    }
                } catch (error) {
                    console.error('Erreur création carte pour', coin, ':', error);
                }
            });
            
            const timestampEl = document.getElementById('timestamp');
            if (timestampEl) {
                timestampEl.textContent = 'Dernière mise à jour : ' + new Date().toLocaleString('fr-FR');
            }
        }

        function refreshAllSignals() {
            fetch('/api/signals/all')
                .then(response => {
                    if (!response.ok) {
                        throw new Error('HTTP ' + response.status);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('Données reçues:', data);
                    if (data.error) {
                        console.error('Erreur API:', data.error);
                        document.getElementById('coins-grid').innerHTML = '<div class="loading">Erreur: ' + data.error + '</div>';
                    } else if (!data.signals || Object.keys(data.signals).length === 0) {
                        console.warn('Aucun signal dans les données');
                        document.getElementById('coins-grid').innerHTML = '<div class="loading">Aucun signal disponible</div>';
                    } else {
                        console.log('Signaux trouvés:', Object.keys(data.signals));
                        updateDisplay(data.signals);
                    }
                })
                .catch(error => {
                    console.error('Erreur fetch:', error);
                    document.getElementById('coins-grid').innerHTML = '<div class="loading" style="color: #f87171;">Erreur de connexion: ' + error.message + '</div>';
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

        // Gestion des onglets d'ordres
        let currentOrdersTab = 'pending';
        
        function showOrdersTab(tab) {
            currentOrdersTab = tab;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            refreshOrders();
        }
        
        function createOrderCard(order) {
            const status = order.status.toLowerCase();
            const signalClass = order.signal === 'ACHAT' ? 'buy' : 'sell';
            const pnl = order.pnl_percent || 0;
            const pnlClass = pnl > 0 ? 'pnl-positive' : pnl < 0 ? 'pnl-negative' : '';
            
            let actionsHtml = '';
            if (status === 'pending') {
                const acceptId = order.order_id.replace(/'/g, "\\'");
                const rejectId = order.order_id.replace(/'/g, "\\'");
                actionsHtml = `
                    <div class="order-actions">
                        <button class="order-btn accept" onclick="acceptOrder('${acceptId}')">✅ Accepter</button>
                        <button class="order-btn reject" onclick="rejectOrder('${rejectId}')">❌ Rejeter</button>
                    </div>
                `;
            } else if (status === 'accepted') {
                const executeId = order.order_id.replace(/'/g, "\\'");
                actionsHtml = `
                    <div class="order-actions">
                        <button class="order-btn execute" onclick="executeOrder('${executeId}')">🚀 Exécuter</button>
                    </div>
                `;
            }
            
            return `
                <div class="order-card ${status}">
                    <div class="order-header">
                        <div class="order-info">
                            <div class="order-coin">${order.coin}</div>
                                <div>
                                <span class="order-signal ${signalClass}">${order.signal}</span>
                                <span class="order-status ${status}">${getStatusLabel(status)}</span>
                                </div>
                            </div>
                        ${order.confidence_score ? `<div style="text-align: right;">
                            <div style="font-size: 0.8em; opacity: 0.7;">Confiance</div>
                            <div style="font-weight: bold;">${order.confidence_score.toFixed(0)}/100</div>
                        </div>` : ''}
                                </div>
                    <div class="order-details">
                        <div class="order-detail-item">
                            <div class="order-detail-label">Prix d'entrée</div>
                            <div class="order-detail-value">$${order.entry_price.toFixed(2)}</div>
                            </div>
                        <div class="order-detail-item">
                            <div class="order-detail-label">Stop Loss</div>
                            <div class="order-detail-value">$${order.stop_loss.toFixed(2)} (${order.stop_loss_percent}%)</div>
                        </div>
                        <div class="order-detail-item">
                            <div class="order-detail-label">Take Profit</div>
                            <div class="order-detail-value">$${order.take_profit.toFixed(2)} (${order.take_profit_percent}%)</div>
                            </div>
                        <div class="order-detail-item">
                            <div class="order-detail-label">Ratio R/R</div>
                            <div class="order-detail-value">${order.risk_reward_ratio.toFixed(2)}:1</div>
                            </div>
                        ${order.exit_price ? `
                        <div class="order-detail-item">
                            <div class="order-detail-label">Prix de sortie</div>
                            <div class="order-detail-value">$${order.exit_price.toFixed(2)}</div>
                        </div>
                        <div class="order-detail-item">
                            <div class="order-detail-label">P&L</div>
                            <div class="order-detail-value ${pnlClass}">${pnl > 0 ? '+' : ''}${pnl.toFixed(2)}%</div>
                                </div>
                        ` : ''}
                                </div>
                    ${actionsHtml}
                    ${order.reasons && order.reasons.length > 0 ? `
                        <div style="margin-top: 10px; font-size: 0.8em; opacity: 0.7;">
                            Raisons: ${order.reasons.slice(0, 2).join(', ')}${order.reasons.length > 2 ? '...' : ''}
                            </div>
                            ` : ''}
                    </div>
                `;
        }
        
        function getStatusLabel(status) {
            const labels = {
                'pending': '⏳ En Attente',
                'accepted': '✅ Accepté',
                'executed': '🚀 Exécuté',
                'closed': '🔒 Fermé',
                'rejected': '❌ Rejeté'
            };
            return labels[status] || status.toUpperCase();
        }
        
        function updateOrdersDisplay(ordersData) {
            const stats = ordersData.statistics;
            const orders = ordersData.orders;
            
            // Mettre à jour les statistiques
            document.getElementById('stat-winrate').textContent = stats.winrate > 0 ? stats.winrate.toFixed(1) + '%' : '-';
            document.getElementById('stat-winrate').className = 'stat-value ' + (stats.winrate >= 50 ? 'positive' : 'negative');
            
            document.getElementById('stat-profit-factor').textContent = stats.profit_factor > 0 ? stats.profit_factor.toFixed(2) : '-';
            document.getElementById('stat-profit-factor').className = 'stat-value ' + (stats.profit_factor >= 1.3 ? 'positive' : 'negative');
            
            document.getElementById('stat-total-trades').textContent = stats.total_trades || 0;
            document.getElementById('stat-total-pnl').textContent = stats.total_pnl ? (stats.total_pnl > 0 ? '+' : '') + stats.total_pnl.toFixed(2) + '%' : '-';
            document.getElementById('stat-total-pnl').className = 'stat-value ' + (stats.total_pnl > 0 ? 'positive' : 'negative');
            
            // Mettre à jour les compteurs
            document.getElementById('count-pending').textContent = orders.pending.length;
            document.getElementById('count-accepted').textContent = orders.accepted.length;
            document.getElementById('count-executed').textContent = orders.executed.length;
            document.getElementById('count-closed').textContent = orders.closed.length;
            
            // Afficher les ordres selon l'onglet actif
            const ordersList = document.getElementById('orders-list');
            let ordersToShow = [];
            
            switch(currentOrdersTab) {
                case 'pending':
                    ordersToShow = orders.pending;
                    break;
                case 'accepted':
                    ordersToShow = orders.accepted;
                    break;
                case 'executed':
                    ordersToShow = orders.executed;
                    break;
                case 'closed':
                    ordersToShow = orders.closed;
                    break;
            }
            
            if (ordersToShow.length === 0) {
                ordersList.innerHTML = '<div class="loading">Aucun ordre dans cette catégorie</div>';
            } else {
                ordersList.innerHTML = ordersToShow.map(order => createOrderCard(order)).join('');
            }
        }
        
        function refreshOrders() {
            fetch('/api/orders')
                .then(response => response.json())
                .then(data => {
                    updateOrdersDisplay(data);
                })
                .catch(error => {
                    console.error('Erreur chargement ordres:', error);
                });
        }
        
        function acceptOrder(orderId) {
            fetch(`/api/orders/${orderId}/accept`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        refreshOrders();
                    } else {
                        alert('Erreur: ' + (data.error || 'Impossible d\\'accepter l\\'ordre'));
                    }
                })
                .catch(error => {
                    console.error('Erreur:', error);
                    alert('Erreur lors de l\\'acceptation de l\\'ordre');
                });
        }
        
        function rejectOrder(orderId) {
            if (confirm('Êtes-vous sûr de vouloir rejeter cet ordre ?')) {
                fetch(`/api/orders/${orderId}/reject`, { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ reason: 'Rejeté manuellement' })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        refreshOrders();
                    } else {
                        alert('Erreur: ' + (data.error || 'Impossible de rejeter l\\'ordre'));
                    }
                })
                .catch(error => {
                console.error('Erreur:', error);
                    alert('Erreur lors du rejet de l\\'ordre');
                });
            }
        }
        
        function executeOrder(orderId) {
            fetch(`/api/orders/${orderId}/execute`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        refreshOrders();
                    } else {
                        alert('Erreur: ' + (data.error || 'Impossible d\\'exécuter l\\'ordre'));
                    }
                })
                .catch(error => {
                    console.error('Erreur:', error);
                    alert('Erreur lors de l\\'exécution de l\\'ordre');
                });
        }
        
        // Initialisation - Attendre que le DOM soit prêt
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                console.log('DOM chargé, initialisation...');
                refreshAllSignals();
                refreshOrders();
                if (autoRefresh) {
                    refreshInterval = setInterval(() => {
                        refreshAllSignals();
                        refreshOrders();
                    }, 5000);
                }
            });
        } else {
            // DOM déjà chargé
            console.log('DOM déjà chargé, initialisation immédiate...');
            refreshAllSignals();
            refreshOrders();
            if (autoRefresh) {
                refreshInterval = setInterval(() => {
                    refreshAllSignals();
                    refreshOrders();
                }, 5000);
            }
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
    global current_signals, last_update, monitoring_active, current_positions
    
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
                        
                        # Évaluer l'opportunité d'entrée
                        should_enter, order_details, confidence, rejection_reasons = decision_engine.evaluate_entry_opportunity(
                            coin, analysis, current_positions
                        )
                        
                        if should_enter:
                            # Vérifier si un ordre similaire n'existe pas déjà
                            pending_orders = order_manager.get_pending_orders()
                            existing_order = None
                            for order in pending_orders:
                                if (order['coin'] == coin and 
                                    order['signal'] == order_details['signal'] and
                                    abs(order['entry_price'] - order_details['entry_price']) / order_details['entry_price'] < 0.01):
                                    existing_order = order
                                    break
                            
                            if not existing_order:
                                order_id = order_manager.add_order(order_details)
                                logger.info(f"📝 Nouvel ordre créé: {order_id} - {coin} {order_details['signal']} @ ${order_details['entry_price']:.2f} (confiance: {confidence:.1f})")
                
                except Exception as e:
                    logger.error(f"Erreur analyse {coin}: {e}")
            
            # Mettre à jour les positions actives
            executed_orders = order_manager.executed_orders
            current_positions = {order['coin']: order for order in executed_orders}
            
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

@app.route('/api/orders')
def get_orders():
    """API pour récupérer tous les ordres"""
    all_orders = order_manager.get_all_orders()
    stats = order_manager.get_statistics()
    return jsonify({
        'orders': all_orders,
        'statistics': stats
    })

@app.route('/api/orders/<order_id>/accept', methods=['POST'])
def accept_order(order_id):
    """API pour accepter un ordre"""
    if order_manager.accept_order(order_id):
        return jsonify({'success': True, 'message': f'Ordre {order_id} accepté'})
    return jsonify({'success': False, 'error': 'Ordre non trouvé'}), 404

@app.route('/api/orders/<order_id>/reject', methods=['POST'])
def reject_order(order_id):
    """API pour rejeter un ordre"""
    data = request.get_json() or {}
    reason = data.get('reason', 'Rejeté manuellement')
    if order_manager.reject_order(order_id, reason):
        return jsonify({'success': True, 'message': f'Ordre {order_id} rejeté'})
    return jsonify({'success': False, 'error': 'Ordre non trouvé'}), 404

@app.route('/api/orders/<order_id>/execute', methods=['POST'])
def execute_order(order_id):
    """API pour exécuter un ordre"""
    if order_manager.execute_order(order_id):
        return jsonify({'success': True, 'message': f'Ordre {order_id} exécuté'})
    return jsonify({'success': False, 'error': 'Ordre non trouvé'}), 404

@app.route('/api/performance')
def get_performance():
    """API pour récupérer l'analyse de performance"""
    analysis = performance_analyzer.analyze_performance()
    return jsonify(analysis)

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

