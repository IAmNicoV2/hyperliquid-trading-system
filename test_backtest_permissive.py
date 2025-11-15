"""Test avec paramètres plus permissifs pour générer des trades"""
import logging
from backtest import ScalpingBacktest

# Réduire les logs
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

def test_permissive():
    """Test avec threshold réduit pour générer des trades"""
    print("="*70)
    print("🧪 TEST BACKTEST AVEC PARAMÈTRES PERMISSIFS")
    print("="*70)
    
    # Activer mode rapide
    try:
        import config
        config.BACKTEST_FAST_MODE = True
        # Sauvegarder les valeurs originales
        original_threshold = getattr(config, 'SIGNAL_QUALITY_THRESHOLD', 82)
        original_volume = getattr(config, 'MIN_VOLUME_MULTIPLIER', 2.5)
        
        # Réduire temporairement pour générer des trades
        config.SIGNAL_QUALITY_THRESHOLD = 70  # Réduire de 82 à 70
        config.MIN_VOLUME_MULTIPLIER = 2.0    # Réduire de 2.5 à 2.0
        
        print(f"\n📊 Paramètres ajustés:")
        print(f"   - Signal Quality Threshold: {original_threshold} → {config.SIGNAL_QUALITY_THRESHOLD}")
        print(f"   - Volume Multiplier: {original_volume} → {config.MIN_VOLUME_MULTIPLIER}")
        print(f"   - Période: 7 jours (mode rapide)")
    except Exception as e:
        print(f"⚠️  Erreur config: {e}")
    
    bt = ScalpingBacktest()
    
    print("\n⏳ Démarrage du backtest...")
    from datetime import datetime
    start_time = datetime.now()
    
    # Utiliser threshold réduit dans le run
    results = bt.run('BTC', signal_quality_threshold=70)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Restaurer les valeurs originales
    try:
        import config
        config.SIGNAL_QUALITY_THRESHOLD = original_threshold
        config.MIN_VOLUME_MULTIPLIER = original_volume
    except:
        pass
    
    if 'error' not in results:
        print(f"\n✅ Backtest terminé en {duration:.1f} secondes")
        print("\n" + "="*70)
        print("📊 RÉSULTATS DÉTAILLÉS")
        print("="*70)
        
        total_trades = results.get('total_trades', 0)
        winrate = results.get('winrate', 0)
        pf = results.get('profit_factor', 0)
        roi = results.get('roi', 0)
        dd = results.get('max_drawdown', 0)
        final_capital = results.get('final_capital', 0)
        
        print(f"\n💰 CAPITAL:")
        print(f"   Initial: ${results.get('initial_capital', 0):,.2f}")
        print(f"   Final:   ${final_capital:,.2f}")
        print(f"   P&L Net: ${results.get('total_pnl', 0):,.2f} ({roi:+.2f}%)")
        
        print(f"\n📈 STATISTIQUES:")
        print(f"   Total Trades: {total_trades}")
        print(f"   Gagnants: {results.get('winning_trades', 0)}")
        print(f"   Perdants: {results.get('losing_trades', 0)}")
        print(f"   Winrate: {winrate:.2f}%")
        print(f"   Profit Factor: {pf:.2f}")
        print(f"   Max Drawdown: {dd:.2f}%")
        
        if total_trades > 0:
            print(f"\n💵 P&L:")
            print(f"   Gain moyen: ${results.get('avg_win', 0):,.2f}")
            print(f"   Perte moyenne: ${results.get('avg_loss', 0):,.2f}")
            print(f"   Frais totaux: ${results.get('total_fees', 0):,.2f}")
            
            # Validation
            print(f"\n✅ VALIDATION:")
            print(f"   Winrate >45%     : {'✅' if winrate > 45 else '❌'} ({winrate:.1f}%)")
            print(f"   Profit Factor>1.2: {'✅' if pf > 1.2 else '❌'} ({pf:.2f})")
            print(f"   Drawdown <15%    : {'✅' if dd < 15 else '❌'} ({dd:.1f}%)")
            print(f"   Return >0%       : {'✅' if roi > 0 else '❌'} ({roi:+.1f}%)")
            
            # Analyse des trades perdants
            if hasattr(bt, 'closed_trades') and bt.closed_trades:
                losing = [t for t in bt.closed_trades if t['pnl_net'] < 0]
                if losing:
                    print(f"\n🔍 ANALYSE RAPIDE:")
                    print(f"   Trades perdants: {len(losing)}")
                    avg_loss = sum(t['pnl_net'] for t in losing) / len(losing)
                    print(f"   Perte moyenne: ${avg_loss:.2f}")
                    
                    # Raison principale
                    exit_reasons = {}
                    for t in losing:
                        reason = t.get('exit_reason', 'UNKNOWN')
                        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
                    main_reason = max(exit_reasons.items(), key=lambda x: x[1])
                    print(f"   Raison principale: {main_reason[0]} ({main_reason[1]} fois)")
        else:
            print("\n⚠️  Aucun trade généré avec ces paramètres")
            print("   Les filtres sont encore trop stricts.")
            print("   Suggestions:")
            print("   - Réduire SIGNAL_QUALITY_THRESHOLD à 65")
            print("   - Réduire MIN_VOLUME_MULTIPLIER à 1.5")
            print("   - Tester sur période plus longue (30 jours)")
    else:
        print(f"❌ Erreur: {results['error']}")

if __name__ == "__main__":
    test_permissive()

