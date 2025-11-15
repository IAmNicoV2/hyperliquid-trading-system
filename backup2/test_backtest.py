"""Script de test rapide pour le backtest avec optimisations"""
import logging
from backtest import ScalpingBacktest

logging.basicConfig(level=logging.WARNING)  # Réduire les logs

print("🚀 Démarrage du backtest optimisé...")
bt = ScalpingBacktest()

# Test 1 : Backtest standard
print("\n" + "="*60)
print("TEST 1: Backtest standard avec paramètres optimisés")
print("="*60)
results = bt.run('BTC')

if 'error' not in results:
    print(f"\n📊 Résultats:")
    print(f"   Total Trades: {results.get('total_trades', 0)}")
    print(f"   Winrate: {results.get('winrate', 0):.2f}%")
    print(f"   Profit Factor: {results.get('profit_factor', 0):.2f}")
    print(f"   ROI: {results.get('roi', 0):.2f}%")
    print(f"   Max Drawdown: {results.get('max_drawdown', 0):.2f}%")
    
    # Test 2 : Optimisation paramètres (optionnel - prend du temps)
    if results.get('winrate', 0) < 50:
        print("\n" + "="*60)
        print("TEST 2: Optimisation paramètres (grid search)")
        print("="*60)
        print("⚠️  Grid search désactivé par défaut (prend du temps)")
        print("   Pour activer, décommenter le code ci-dessous")
        
        # param_ranges = {
        #     'signal_threshold': [80, 82, 85],
        #     'rsi_period': [11, 14, 17],
        #     'volume_multiplier': [2.5, 3.0]
        # }
        # best_params, best_metrics, _ = bt.optimize_parameters('BTC', param_ranges)
        # if best_params:
        #     print(f"\n🏆 MEILLEURS PARAMÈTRES : {best_params}")
        #     print(f"Winrate : {best_metrics.get('winrate', 0):.1f}%")
        #     print(f"Profit Factor : {best_metrics.get('profit_factor', 0):.2f}")
else:
    print(f"❌ Erreur: {results['error']}")

