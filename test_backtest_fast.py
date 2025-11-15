"""Script de test rapide optimisé pour le backtest"""
import logging
from backtest import ScalpingBacktest
from datetime import datetime, timedelta

# Réduire les logs pour accélérer
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

def test_fast_backtest():
    """Test rapide avec période réduite"""
    print("="*70)
    print("🚀 BACKTEST RAPIDE OPTIMISÉ")
    print("="*70)
    
    print("\n📊 Configuration:")
    print("   - Période: 7 jours (au lieu de 30)")
    print("   - Timeframe: 5m")
    print("   - Échantillonnage: 1/2 (traitement accéléré)")
    print("   - Logs réduits")
    
    # Activer le mode rapide dans config
    try:
        import config
        config.BACKTEST_FAST_MODE = True
    except:
        pass
    
    bt = ScalpingBacktest()
    
    print("\n⏳ Démarrage du backtest...")
    start_time = datetime.now()
    
    results = bt.run('BTC')
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    if 'error' not in results:
        print(f"\n✅ Backtest terminé en {duration:.1f} secondes")
        print("\n" + "="*70)
        print("📊 RÉSULTATS")
        print("="*70)
        print(f"Total Trades: {results.get('total_trades', 0)}")
        print(f"Winrate: {results.get('winrate', 0):.2f}%")
        print(f"Profit Factor: {results.get('profit_factor', 0):.2f}")
        print(f"ROI: {results.get('roi', 0):.2f}%")
        print(f"Max Drawdown: {results.get('max_drawdown', 0):.2f}%")
        print(f"Capital Final: ${results.get('final_capital', 0):,.2f}")
        
        # Validation
        print("\n✅ VALIDATION:")
        winrate = results.get('winrate', 0)
        pf = results.get('profit_factor', 0)
        dd = results.get('max_drawdown', 0)
        roi = results.get('roi', 0)
        
        print(f"  Winrate >45%     : {'✅' if winrate > 45 else '❌'} ({winrate:.1f}%)")
        print(f"  Profit Factor>1.2: {'✅' if pf > 1.2 else '❌'} ({pf:.2f})")
        print(f"  Drawdown <15%    : {'✅' if dd < 15 else '❌'} ({dd:.1f}%)")
        print(f"  Return >0%       : {'✅' if roi > 0 else '❌'} ({roi:+.1f}%)")
        
        # Analyse des trades perdants si disponible
        if hasattr(bt, 'closed_trades') and bt.closed_trades:
            losing = [t for t in bt.closed_trades if t['pnl_net'] < 0]
            if losing:
                print(f"\n🔍 Analyse rapide:")
                print(f"   Trades perdants: {len(losing)}")
                avg_loss = sum(t['pnl_net'] for t in losing) / len(losing)
                print(f"   Perte moyenne: ${avg_loss:.2f}")
                
                # Raison principale de sortie
                exit_reasons = {}
                for t in losing:
                    reason = t.get('exit_reason', 'UNKNOWN')
                    exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
                main_reason = max(exit_reasons.items(), key=lambda x: x[1])
                print(f"   Raison principale: {main_reason[0]} ({main_reason[1]} fois)")
    else:
        print(f"❌ Erreur: {results['error']}")

if __name__ == "__main__":
    test_fast_backtest()

