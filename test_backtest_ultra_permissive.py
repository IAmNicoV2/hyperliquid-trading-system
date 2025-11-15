"""Test ultra-permissif pour générer des trades"""
import logging
from backtest import ScalpingBacktest

logging.basicConfig(level=logging.WARNING)

def test_ultra_permissive():
    """Test avec tous les paramètres assouplis"""
    print("="*70)
    print("🧪 TEST ULTRA-PERMISSIF")
    print("="*70)
    
    try:
        import config
        config.BACKTEST_FAST_MODE = True
        
        # Sauvegarder valeurs originales
        original = {
            'threshold': getattr(config, 'SIGNAL_QUALITY_THRESHOLD', 82),
            'volume': getattr(config, 'MIN_VOLUME_MULTIPLIER', 2.5),
            'spread': getattr(config, 'MAX_SPREAD_PERCENT', 0.03),
            'context_checks': getattr(config, 'VALIDATION_CONTEXT_MIN_CHECKS', 5)
        }
        
        # Paramètres ultra-permissifs
        config.SIGNAL_QUALITY_THRESHOLD = 60
        config.MIN_VOLUME_MULTIPLIER = 1.0  # Réduire à 1.0x (volume normal)
        config.MAX_SPREAD_PERCENT = 0.05
        config.ATR_MIN_PERCENT = 0.3  # Réduire ATR min
        config.ATR_MAX_PERCENT = 1.5  # Augmenter ATR max
        config.VALIDATION_CONTEXT_MIN_CHECKS = 4  # 4/6 au lieu de 5/6
        config.SKIP_CONTEXT_VALIDATION = True  # Désactiver validation contexte pour tests
        config.SKIP_VOLUME_FILTER = True  # Désactiver filtre volume pour tests
        config.SKIP_ATR_FILTER = True  # Désactiver filtre ATR pour tests
        
        print(f"\n📊 Paramètres ultra-permissifs:")
        print(f"   - Signal Quality: {original['threshold']} → {config.SIGNAL_QUALITY_THRESHOLD}")
        print(f"   - Volume: {original['volume']} → {config.MIN_VOLUME_MULTIPLIER}")
        print(f"   - Spread: {original['spread']}% → {config.MAX_SPREAD_PERCENT}%")
        print(f"   - ATR Range: {getattr(config, 'ATR_MIN_PERCENT', 0.5)}% - {getattr(config, 'ATR_MAX_PERCENT', 1.2)}%")
        print(f"   - Context Checks: {original['context_checks']}/6 → {config.VALIDATION_CONTEXT_MIN_CHECKS}/6")
        print(f"   - Skip Context Validation: {config.SKIP_CONTEXT_VALIDATION}")
    except Exception as e:
        print(f"⚠️  Erreur config: {e}")
        original = {}
    
    bt = ScalpingBacktest()
    
    print("\n⏳ Démarrage du backtest...")
    from datetime import datetime
    start_time = datetime.now()
    
    results = bt.run('BTC', signal_quality_threshold=60)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Restaurer valeurs originales
    try:
        import config
        for key, value in original.items():
            setattr(config, key.upper() if key != 'context_checks' else 'VALIDATION_CONTEXT_MIN_CHECKS', value)
    except:
        pass
    
    if 'error' not in results:
        print(f"\n✅ Backtest terminé en {duration:.1f} secondes")
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
            print("\n📊 Statistiques de filtres:")
            stats = results.get('debug_stats', {})
            print(f"   Total signaux: {stats.get('total_signals', 0)}")
            print(f"   NEUTRE: {stats.get('neutral_signals', 0)}")
            print(f"   Qualité insuffisante: {stats.get('quality_too_low', 0)}")
            print(f"   Filtres échoués: {stats.get('filters_failed', 0)}")
            print(f"   Positions ouvertes: {stats.get('positions_opened', 0)}")
    else:
        print(f"❌ Erreur: {results['error']}")

if __name__ == "__main__":
    test_ultra_permissive()

