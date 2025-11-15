"""Script de test rapide pour le backtest"""
import logging
from backtest import ScalpingBacktest

logging.basicConfig(level=logging.WARNING)  # Réduire les logs

print("🚀 Démarrage du backtest...")
bt = ScalpingBacktest()
results = bt.run('BTC')

if 'error' not in results:
    print(f"\n📊 Résultats:")
    print(f"   Total Trades: {results.get('total_trades', 0)}")
    print(f"   Winrate: {results.get('winrate', 0):.2f}%")
    print(f"   Profit Factor: {results.get('profit_factor', 0):.2f}")
    print(f"   ROI: {results.get('roi', 0):.2f}%")
    print(f"   Max Drawdown: {results.get('max_drawdown', 0):.2f}%")
else:
    print(f"❌ Erreur: {results['error']}")

