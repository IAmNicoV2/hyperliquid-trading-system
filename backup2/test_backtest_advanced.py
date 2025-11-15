"""Script de test approfondi pour le backtest avec analyse détaillée"""
import logging
from backtest import ScalpingBacktest
from datetime import datetime, timedelta
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def analyze_trade_patterns(backtest):
    """Analyse approfondie des patterns de trades"""
    if not backtest.closed_trades:
        print("❌ Aucun trade à analyser")
        return
    
    trades = backtest.closed_trades
    winning_trades = [t for t in trades if t['pnl_net'] > 0]
    losing_trades = [t for t in trades if t['pnl_net'] <= 0]
    
    print("\n" + "="*70)
    print("📈 ANALYSE APPROFONDIE DES PATTERNS")
    print("="*70)
    
    # 1. Analyse par type de signal
    print("\n1️⃣ PAR TYPE DE SIGNAL:")
    buy_trades = [t for t in trades if t['type'] in ['ACHAT', 'BUY']]
    sell_trades = [t for t in trades if t['type'] in ['VENTE', 'SELL']]
    
    if buy_trades:
        buy_wins = sum(1 for t in buy_trades if t['pnl_net'] > 0)
        buy_winrate = (buy_wins / len(buy_trades)) * 100
        buy_avg = sum(t['pnl_net'] for t in buy_trades) / len(buy_trades)
        print(f"   BUY: {len(buy_trades)} trades, Winrate: {buy_winrate:.1f}%, PnL moyen: ${buy_avg:.2f}")
    
    if sell_trades:
        sell_wins = sum(1 for t in sell_trades if t['pnl_net'] > 0)
        sell_winrate = (sell_wins / len(sell_trades)) * 100
        sell_avg = sum(t['pnl_net'] for t in sell_trades) / len(sell_trades)
        print(f"   SELL: {len(sell_trades)} trades, Winrate: {sell_winrate:.1f}%, PnL moyen: ${sell_avg:.2f}")
    
    # 2. Analyse par raison de sortie
    print("\n2️⃣ PAR RAISON DE SORTIE:")
    exit_reasons = {}
    for trade in trades:
        reason = trade['exit_reason']
        if reason not in exit_reasons:
            exit_reasons[reason] = {'total': 0, 'wins': 0, 'total_pnl': 0}
        exit_reasons[reason]['total'] += 1
        if trade['pnl_net'] > 0:
            exit_reasons[reason]['wins'] += 1
        exit_reasons[reason]['total_pnl'] += trade['pnl_net']
    
    for reason, data in sorted(exit_reasons.items(), key=lambda x: -x[1]['total']):
        winrate = (data['wins'] / data['total']) * 100 if data['total'] > 0 else 0
        avg_pnl = data['total_pnl'] / data['total']
        print(f"   {reason}: {data['total']} trades, Winrate: {winrate:.1f}%, PnL moyen: ${avg_pnl:.2f}")
    
    # 3. Analyse par durée
    print("\n3️⃣ PAR DURÉE:")
    duration_buckets = {
        '<5min': [],
        '5-15min': [],
        '15-30min': [],
        '>30min': []
    }
    
    for trade in trades:
        duration = trade.get('duration_min', 0)
        if duration < 5:
            duration_buckets['<5min'].append(trade)
        elif duration < 15:
            duration_buckets['5-15min'].append(trade)
        elif duration < 30:
            duration_buckets['15-30min'].append(trade)
        else:
            duration_buckets['>30min'].append(trade)
    
    for bucket, bucket_trades in duration_buckets.items():
        if bucket_trades:
            wins = sum(1 for t in bucket_trades if t['pnl_net'] > 0)
            winrate = (wins / len(bucket_trades)) * 100
            avg_pnl = sum(t['pnl_net'] for t in bucket_trades) / len(bucket_trades)
            print(f"   {bucket}: {len(bucket_trades)} trades, Winrate: {winrate:.1f}%, PnL moyen: ${avg_pnl:.2f}")
    
    # 4. Analyse des meilleurs/pires trades
    print("\n4️⃣ TOP 5 MEILLEURS TRADES:")
    best_trades = sorted(winning_trades, key=lambda x: x['pnl_net'], reverse=True)[:5]
    for i, trade in enumerate(best_trades, 1):
        print(f"   {i}. {trade['type']} {trade['coin']}: ${trade['pnl_net']:.2f} ({trade['pnl_percent']:+.2f}%) - {trade['exit_reason']} - {trade['duration_min']:.1f}min")
    
    print("\n5️⃣ TOP 5 PIRE TRADES:")
    worst_trades = sorted(losing_trades, key=lambda x: x['pnl_net'])[:5]
    for i, trade in enumerate(worst_trades, 1):
        print(f"   {i}. {trade['type']} {trade['coin']}: ${trade['pnl_net']:.2f} ({trade['pnl_percent']:+.2f}%) - {trade['exit_reason']} - {trade['duration_min']:.1f}min")
    
    # 5. Ratio gain/perte
    if winning_trades and losing_trades:
        avg_win = sum(t['pnl_net'] for t in winning_trades) / len(winning_trades)
        avg_loss = abs(sum(t['pnl_net'] for t in losing_trades) / len(losing_trades))
        ratio = avg_win / avg_loss if avg_loss > 0 else 0
        print(f"\n6️⃣ RATIO GAIN/PERTE: {ratio:.2f} (Gain moyen: ${avg_win:.2f}, Perte moyenne: ${avg_loss:.2f})")
        
        # Calcul winrate minimum nécessaire
        min_winrate = (1 / (1 + ratio)) * 100
        print(f"   Winrate minimum pour break-even: {min_winrate:.1f}%")
        print(f"   Winrate actuel: {(len(winning_trades) / len(trades)) * 100:.1f}%")

def test_multiple_coins():
    """Tester sur plusieurs coins"""
    coins = ['BTC', 'ETH', 'SOL']
    results = {}
    
    print("\n" + "="*70)
    print("🪙 TEST MULTI-COINS")
    print("="*70)
    
    for coin in coins:
        print(f"\n{'='*70}")
        print(f"TEST {coin}")
        print(f"{'='*70}")
        
        bt = ScalpingBacktest()
        metrics = bt.run(coin=coin)
        
        if 'error' not in metrics:
            results[coin] = metrics
            print(f"\n✅ {coin}: Winrate {metrics.get('winrate', 0):.1f}%, PF {metrics.get('profit_factor', 0):.2f}")
        else:
            print(f"❌ {coin}: {metrics['error']}")
    
    # Comparaison
    if results:
        print("\n" + "="*70)
        print("📊 COMPARAISON MULTI-COINS")
        print("="*70)
        print(f"{'Coin':<8} {'Trades':<8} {'Winrate':<10} {'PF':<8} {'ROI':<10} {'DD':<8}")
        print("-"*70)
        for coin, metrics in results.items():
            print(f"{coin:<8} {metrics.get('total_trades', 0):<8} "
                  f"{metrics.get('winrate', 0):>6.1f}%   "
                  f"{metrics.get('profit_factor', 0):>6.2f}   "
                  f"{metrics.get('roi', 0):>7.2f}%   "
                  f"{metrics.get('max_drawdown', 0):>6.2f}%")

def optimize_parameters_quick():
    """Optimisation rapide des paramètres clés"""
    print("\n" + "="*70)
    print("🔍 OPTIMISATION PARAMÈTRES (GRID SEARCH RAPIDE)")
    print("="*70)
    
    bt = ScalpingBacktest()
    
    # Paramètres réduits pour test rapide
    param_ranges = {
        'signal_threshold': [80, 82, 85],  # 3 valeurs
        'volume_multiplier': [2.0, 2.5, 3.0],  # 3 valeurs
        'max_spread': [0.02, 0.03, 0.04]  # 3 valeurs
    }
    
    print(f"⚠️  Grid search: {3*3*3} = 27 combinaisons à tester")
    print("   Cela peut prendre plusieurs minutes...")
    
    response = input("\nContinuer? (o/n): ")
    if response.lower() != 'o':
        print("❌ Grid search annulé")
        return
    
    best_params, best_metrics, all_results = bt.optimize_parameters('BTC', param_ranges)
    
    if best_params:
        print("\n" + "="*70)
        print("🏆 MEILLEURS PARAMÈTRES TROUVÉS")
        print("="*70)
        print(f"Paramètres: {best_params}")
        print(f"Winrate: {best_metrics.get('winrate', 0):.1f}%")
        print(f"Profit Factor: {best_metrics.get('profit_factor', 0):.2f}")
        print(f"ROI: {best_metrics.get('roi', 0):.2f}%")
        print(f"Max Drawdown: {best_metrics.get('max_drawdown', 0):.2f}%")
        print(f"Total Trades: {best_metrics.get('total_trades', 0)}")
        
        # Top 5 résultats
        print("\n📊 TOP 5 RÉSULTATS:")
        sorted_results = sorted(all_results, key=lambda x: x['profit_factor'], reverse=True)[:5]
        for i, result in enumerate(sorted_results, 1):
            print(f"   {i}. PF: {result['profit_factor']:.2f}, WR: {result['winrate']:.1f}%, "
                  f"Params: {result['params']}")
    else:
        print("❌ Aucun paramètre optimal trouvé (winrate <45% ou drawdown >15%)")

def main():
    """Fonction principale"""
    print("="*70)
    print("🚀 BACKTEST APPROFONDI - ANALYSE COMPLÈTE")
    print("="*70)
    
    # Test 1: Backtest standard avec analyse
    print("\n" + "="*70)
    print("TEST 1: BACKTEST STANDARD BTC (30 jours)")
    print("="*70)
    
    bt = ScalpingBacktest()
    results = bt.run('BTC')
    
    if 'error' not in results:
        # Analyse approfondie
        analyze_trade_patterns(bt)
        
        # Test 2: Multi-coins (optionnel)
        print("\n" + "="*70)
        response = input("Tester sur plusieurs coins (BTC, ETH, SOL)? (o/n): ")
        if response.lower() == 'o':
            test_multiple_coins()
        
        # Test 3: Optimisation paramètres (optionnel)
        print("\n" + "="*70)
        response = input("Lancer optimisation paramètres (grid search)? (o/n): ")
        if response.lower() == 'o':
            optimize_parameters_quick()
    else:
        print(f"❌ Erreur: {results['error']}")

if __name__ == "__main__":
    main()

