"""
Backtest de la stratégie complète du système de trading
Utilise le système de décision pour tester sur 30 jours
"""

import sys
import os
from datetime import datetime, timedelta
import logging
from typing import Dict, List
from backtest import ScalpingBacktest
from trading_decision import TradingDecisionEngine
from order_manager import OrderManager
from performance_analyzer import PerformanceAnalyzer
import config

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_strategy_backtest(coin: str, days: int = 7) -> Dict:
    """
    Lance un backtest de la stratégie complète pour un coin
    
    Args:
        coin: Symbole du coin (BTC, ETH, etc.)
        days: Nombre de jours à backtester
    
    Returns:
        Dictionnaire avec les résultats du backtest
    """
    print(f"\n{'='*60}")
    print(f"🚀 BACKTEST STRATÉGIE - {coin} ({days} jours)")
    print(f"{'='*60}\n")
    
    try:
        # Initialiser le backtest
        backtest = ScalpingBacktest(initial_capital=config.BACKTEST_INITIAL_CAPITAL)
        
        # Charger les données historiques
        logger.info(f"📥 Chargement des données historiques pour {coin}...")
        candles = backtest.load_historical_data(
            coin=coin,
            interval=config.DEFAULT_INTERVAL,
            days=days
        )
        
        if not candles or len(candles) < 100:
            logger.error(f"❌ Pas assez de données pour {coin}")
            return {
                'coin': coin,
                'error': 'Pas assez de données',
                'candles_count': len(candles) if candles else 0
            }
        
        logger.info(f"✅ {len(candles)} chandeliers chargés")
        
        # Initialiser le générateur de signaux
        from hyperliquid_signals import HyperliquidSignalGenerator
        signal_generator = HyperliquidSignalGenerator(coin=coin, interval=config.DEFAULT_INTERVAL)
        signal_generator.candles = candles
        
        # Initialiser le système de décision
        decision_engine = TradingDecisionEngine()
        order_manager = OrderManager(orders_file=f"backtest_orders_{coin}.json")
        
        # Variables de suivi
        current_positions = {}
        trades_executed = []
        
        # Statistiques de rejet
        rejection_stats = {
            'total_signals': 0,
            'neutral_signals': 0,
            'rejections': {}
        }
        
        logger.info(f"📊 Démarrage du backtest sur {len(candles)} chandeliers...")
        
        total_candles = len(candles)
        start_index = 100  # Période de warm-up
        processed = 0
        last_progress = 0
        
        # Parcourir les chandeliers
        for i in range(start_index, total_candles):
            candle = candles[i]
            timestamp = candle['time']
            current_price = candle['close']
            
            # Mettre à jour les chandeliers du générateur
            signal_generator.candles = candles[:i+1]
            signal_generator.current_price = current_price
            
            # Analyser le marché
            try:
                analysis = signal_generator.analyze()
                
                if 'error' in analysis:
                    continue
                
                signal = analysis.get('signal', 'NEUTRE')
                rejection_stats['total_signals'] += 1
                
                if signal == 'NEUTRE':
                    rejection_stats['neutral_signals'] += 1
                    continue
                
                # Évaluer l'opportunité d'entrée
                should_enter, order_details, confidence, rejection_reasons = decision_engine.evaluate_entry_opportunity(
                    coin, analysis, current_positions, debug=True
                )
                
                # Collecter les statistiques de rejet
                if not should_enter and rejection_reasons:
                    for reason_key, reason_msg in rejection_reasons.items():
                        if reason_key not in rejection_stats['rejections']:
                            rejection_stats['rejections'][reason_key] = 0
                        rejection_stats['rejections'][reason_key] += 1
                
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
                        # Créer l'ordre et l'accepter automatiquement pour le backtest
                        order_id = order_manager.add_order(order_details)
                        order_manager.accept_order(order_id)
                        order_manager.execute_order(order_id)
                        
                        # Enregistrer la position
                        current_positions[coin] = {
                            'order_id': order_id,
                            'entry_price': order_details['entry_price'],
                            'stop_loss': order_details['stop_loss'],
                            'take_profit': order_details['take_profit'],
                            'signal': order_details['signal'],
                            'entry_time': timestamp
                        }
                
                # Vérifier les conditions de sortie pour les positions ouvertes
                if coin in current_positions:
                    position = current_positions[coin]
                    entry_price = position['entry_price']
                    stop_loss = position['stop_loss']
                    take_profit = position['take_profit']
                    signal_type = position['signal']
                    
                    exit_reason = None
                    exit_price = current_price
                    
                    # Vérifier Stop Loss
                    if signal_type == 'ACHAT':
                        if current_price <= stop_loss:
                            exit_reason = 'STOP_LOSS'
                            exit_price = stop_loss
                        elif current_price >= take_profit:
                            exit_reason = 'TAKE_PROFIT'
                            exit_price = take_profit
                    else:  # VENTE
                        if current_price >= stop_loss:
                            exit_reason = 'STOP_LOSS'
                            exit_price = stop_loss
                        elif current_price <= take_profit:
                            exit_reason = 'TAKE_PROFIT'
                            exit_price = take_profit
                    
                    # Vérifier le time stop (10 minutes)
                    entry_time = position['entry_time']
                    time_elapsed = (timestamp - entry_time) / 60  # en minutes
                    if time_elapsed > config.SL_TIME_MINUTES:
                        # Vérifier si on est en profit
                        if signal_type == 'ACHAT':
                            pnl_percent = ((current_price - entry_price) / entry_price) * 100
                        else:
                            pnl_percent = ((entry_price - current_price) / entry_price) * 100
                        
                        if pnl_percent < 0.2:  # Moins de 0.2% de profit après 10 min
                            exit_reason = 'TIME_STOP'
                            exit_price = current_price
                    
                    if exit_reason:
                        # Fermer la position
                        order_manager.close_position(position['order_id'], exit_price, exit_reason)
                        del current_positions[coin]
            
            except Exception as e:
                logger.error(f"Erreur lors de l'analyse {coin} à l'index {i}: {e}")
                continue
            
            # Afficher la progression
            processed = i - start_index + 1
            progress_percent = (processed / (total_candles - start_index)) * 100
            
            # Afficher tous les 5% ou tous les 100 chandeliers
            if progress_percent - last_progress >= 5 or processed % 100 == 0:
                trades_count = len(order_manager.executed_orders) + len(order_manager.closed_positions)
                positions_open = len(current_positions)
                print(f"\r[{coin}] Progression: {progress_percent:.1f}% ({processed}/{total_candles - start_index}) | Trades: {trades_count} | Positions: {positions_open}", end='', flush=True)
                last_progress = progress_percent
        
        print()  # Nouvelle ligne après la progression
        
        # Afficher les statistiques de rejet
        if rejection_stats['total_signals'] > 0:
            print(f"\n{'='*60}")
            print(f"📊 ANALYSE DES REJETS - {coin}")
            print(f"{'='*60}")
            print(f"Total signaux analysés: {rejection_stats['total_signals']}")
            print(f"Signaux NEUTRE: {rejection_stats['neutral_signals']} ({rejection_stats['neutral_signals']/rejection_stats['total_signals']*100:.1f}%)")
            print(f"Signaux ACHAT/VENTE: {rejection_stats['total_signals'] - rejection_stats['neutral_signals']}")
            print(f"\nRaisons de rejet (par ordre de fréquence):")
            
            sorted_rejections = sorted(
                rejection_stats['rejections'].items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            
            for reason_key, count in sorted_rejections[:10]:  # Top 10
                percentage = (count / (rejection_stats['total_signals'] - rejection_stats['neutral_signals'])) * 100
                print(f"  {reason_key:30s}: {count:5d} ({percentage:5.1f}%)")
            print(f"{'='*60}\n")
        
        # Fermer toutes les positions restantes
        for coin_pos, position in current_positions.items():
            last_candle = candles[-1]
            exit_price = last_candle['close']
            order_manager.close_position(position['order_id'], exit_price, 'TIMEOUT')
        
        # Calculer les statistiques
        stats = order_manager.get_statistics()
        analysis = PerformanceAnalyzer(order_manager).analyze_performance()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 RÉSULTATS BACKTEST - {coin}")
        logger.info(f"{'='*60}")
        logger.info(f"Total trades: {stats['total_trades']}")
        logger.info(f"Gagnants: {stats['winning_trades']} ({stats['winrate']:.2f}%)")
        logger.info(f"Perdants: {stats['losing_trades']}")
        logger.info(f"Profit Factor: {stats['profit_factor']:.2f}")
        logger.info(f"P&L Total: {stats['total_pnl']:.2f}%")
        logger.info(f"Gain moyen: {stats['avg_win']:.2f}%")
        logger.info(f"Perte moyenne: {stats['avg_loss']:.2f}%")
        logger.info(f"{'='*60}\n")
        
        return {
            'coin': coin,
            'days': days,
            'candles_analyzed': len(candles),
            'statistics': stats,
            'analysis': analysis,
            'success': True
        }
    
    except Exception as e:
        logger.error(f"❌ Erreur backtest {coin}: {e}", exc_info=True)
        return {
            'coin': coin,
            'error': str(e),
            'success': False
        }

def run_all_coins_backtest(days: int = 7):
    """Lance le backtest pour tous les coins supportés"""
    supported_coins = getattr(config, 'SUPPORTED_COINS', ['BTC', 'ETH', 'SOL', 'HYPE', 'ARB'])
    
    results = {}
    
    for coin in supported_coins:
        result = run_strategy_backtest(coin, days)
        results[coin] = result
    
    # Afficher le résumé global
    print("\n" + "="*80)
    print("📊 RÉSUMÉ GLOBAL - BACKTEST STRATÉGIE (7 JOURS)")
    print("="*80)
    print(f"{'Coin':<8} {'Trades':<8} {'Winrate':<10} {'Profit Factor':<15} {'P&L Total':<12} {'Status'}")
    print("-"*80)
    
    total_trades = 0
    total_wins = 0
    total_losses = 0
    total_pnl = 0.0
    
    for coin, result in results.items():
        if result.get('success'):
            stats = result['statistics']
            total_trades += stats['total_trades']
            total_wins += stats['winning_trades']
            total_losses += stats['losing_trades']
            total_pnl += stats['total_pnl']
            
            winrate = stats['winrate']
            profit_factor = stats['profit_factor']
            status = "✅" if winrate >= 50 and profit_factor >= 1.3 else "⚠️"
            
            print(f"{coin:<8} {stats['total_trades']:<8} {winrate:>6.1f}%   {profit_factor:>6.2f}        {stats['total_pnl']:>+8.2f}%    {status}")
        else:
            print(f"{coin:<8} {'ERROR':<8} {'-':<10} {'-':<15} {'-':<12} {'❌'}")
    
    print("-"*80)
    if total_trades > 0:
        global_winrate = (total_wins / total_trades) * 100
        print(f"{'TOTAL':<8} {total_trades:<8} {global_winrate:>6.1f}%   {'-':<15} {total_pnl:>+8.2f}%    {'✅' if global_winrate >= 50 else '⚠️'}")
    
    print("="*80)
    
    # Recommandations
    print("\n💡 RECOMMANDATIONS:")
    for coin, result in results.items():
        if result.get('success'):
            analysis = result.get('analysis', {})
            recommendations = analysis.get('recommendations', [])
            if recommendations:
                print(f"\n{coin}:")
                for rec in recommendations[:3]:  # Top 3 recommandations
                    print(f"  - {rec}")
    
    return results

if __name__ == '__main__':
    print("\n" + "="*80)
    print("🚀 BACKTEST STRATÉGIE COMPLÈTE - 7 JOURS")
    print("="*80)
    print(f"Coins: {', '.join(getattr(config, 'SUPPORTED_COINS', ['BTC', 'ETH', 'SOL', 'HYPE', 'ARB']))}")
    print(f"Période: 7 jours")
    print(f"Intervalle: {config.DEFAULT_INTERVAL}")
    print(f"Capital initial: ${config.BACKTEST_INITIAL_CAPITAL:,.2f}")
    print("="*80 + "\n")
    
    results = run_all_coins_backtest(days=7)
    
    print("\n✅ Backtest terminé!")
    print("📁 Fichiers d'ordres sauvegardés: backtest_orders_*.json")

