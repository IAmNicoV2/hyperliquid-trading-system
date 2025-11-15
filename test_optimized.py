"""Test avec paramètres optimisés selon recommandations"""
import logging
from backtest import ScalpingBacktest

logging.basicConfig(level=logging.WARNING)

print("="*70)
print("🚀 TEST AVEC PARAMÈTRES OPTIMISÉS")
print("="*70)
print("\n📊 Paramètres appliqués:")
print("   ✅ SL réduit: 0.5-0.8% (au lieu de 0.6-1.0%)")
print("   ✅ Ratio RR: 2:1 (au lieu de 1.5:1)")
print("   ✅ TIME_STOP: 10 min (au lieu de 15 min)")
print("   ✅ Filtres SELL renforcés")
print("   ✅ Threshold: 78 (au lieu de 82)")
print("   ✅ Volume: 2.2x (au lieu de 2.5x)")
print("   ✅ Context checks: 4/6 (au lieu de 5/6)")

bt = ScalpingBacktest()
results = bt.run('BTC')

if 'error' not in results:
    print("\n" + "="*70)
    print("📊 RÉSULTATS")
    print("="*70)
    
    total_trades = results.get('total_trades', 0)
    if total_trades > 0:
        print(f"\n💰 CAPITAL:")
        print(f"   Initial: ${results.get('initial_capital', 0):,.2f}")
        print(f"   Final:   ${results.get('final_capital', 0):,.2f}")
        print(f"   P&L:     ${results.get('total_pnl', 0):,.2f} ({results.get('roi', 0):+.2f}%)")
        
        print(f"\n📈 STATISTIQUES:")
        print(f"   Total Trades: {total_trades}")
        print(f"   Gagnants: {results.get('winning_trades', 0)}")
        print(f"   Perdants: {results.get('losing_trades', 0)}")
        print(f"   Winrate: {results.get('winrate', 0):.2f}%")
        print(f"   Profit Factor: {results.get('profit_factor', 0):.2f}")
        print(f"   Max Drawdown: {results.get('max_drawdown', 0):.2f}%")
        
        if total_trades > 0:
            print(f"\n💵 P&L DÉTAILLÉ:")
            print(f"   Gain moyen: ${results.get('avg_win', 0):,.2f}")
            print(f"   Perte moyenne: ${results.get('avg_loss', 0):,.2f}")
            print(f"   Frais totaux: ${results.get('total_fees', 0):,.2f}")
            
            # Validation
            winrate = results.get('winrate', 0)
            pf = results.get('profit_factor', 0)
            dd = results.get('max_drawdown', 0)
            roi = results.get('roi', 0)
            
            print(f"\n✅ VALIDATION:")
            print(f"   Winrate >45%     : {'✅' if winrate > 45 else '❌'} ({winrate:.1f}%)")
            print(f"   Profit Factor>1.2: {'✅' if pf > 1.2 else '❌'} ({pf:.2f})")
            print(f"   Drawdown <15%    : {'✅' if dd < 15 else '❌'} ({dd:.1f}%)")
            print(f"   Return >0%       : {'✅' if roi > 0 else '❌'} ({roi:+.1f}%)")
    else:
        print("\n⚠️  Aucun trade généré")
        stats = results.get('debug_stats', {})
        print(f"   Signaux analysés: {stats.get('total_signals', 0)}")
        print(f"   NEUTRE: {stats.get('neutral_signals', 0)}")
        print(f"   Qualité insuffisante: {stats.get('quality_too_low', 0)}")
        print(f"   Filtres échoués: {stats.get('filters_failed', 0)}")
else:
    print(f"❌ Erreur: {results['error']}")

