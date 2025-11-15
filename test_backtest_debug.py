"""Test de debug pour comprendre pourquoi aucun trade n'est généré"""
import logging
from backtest import ScalpingBacktest
from hyperliquid_signals import HyperliquidSignalGenerator

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def debug_signals():
    """Analyse pourquoi les signaux ne passent pas les filtres"""
    print("="*70)
    print("🔍 DEBUG - ANALYSE DES SIGNAUX")
    print("="*70)
    
    try:
        import config
        config.BACKTEST_FAST_MODE = True
        # Paramètres très permissifs pour debug
        config.SIGNAL_QUALITY_THRESHOLD = 60
        config.MIN_VOLUME_MULTIPLIER = 1.5
        config.MAX_SPREAD_PERCENT = 0.05
    except:
        pass
    
    # Charger quelques chandeliers
    generator = HyperliquidSignalGenerator(coin='BTC', interval='5m')
    candles = generator.fetch_historical_candles(limit=500)
    
    if not candles:
        print("❌ Impossible de charger les données")
        return
    
    print(f"\n✅ {len(candles)} chandeliers chargés")
    print(f"\n📊 Analyse des 10 derniers chandeliers...\n")
    
    # Analyser les 10 derniers
    for i in range(max(50, len(candles) - 10), len(candles)):
        generator.candles = candles[:i+1]
        generator.current_price = candles[i]['close']
        
        analysis = generator.analyze()
        
        if 'error' in analysis:
            continue
        
        signal = analysis.get('signal', 'NEUTRE')
        signal_quality = generator._calculate_signal_quality(analysis)
        
        # Vérifier les filtres
        should_enter, reason = generator.should_enter_trade(analysis)
        
        indicators = analysis.get('indicators', {})
        current_price = analysis.get('current_price', 0)
        spread = analysis.get('spread', 0.1)
        
        # Volume ratio
        volume_ratio = 0
        if len(candles) >= 20:
            recent_volume = sum(c.get('volume', 0) for c in candles[-5:])
            avg_volume = sum(c.get('volume', 0) for c in candles[-20:]) / 20
            if avg_volume > 0:
                volume_ratio = recent_volume / (avg_volume * 5)
        
        print(f"Chandelier {i}:")
        print(f"  Signal: {signal}")
        print(f"  Qualité: {signal_quality:.1f}/100")
        print(f"  Prix: ${current_price:,.2f}")
        print(f"  Spread: {spread:.3f}%")
        print(f"  Volume ratio: {volume_ratio:.2f}x")
        print(f"  RSI: {indicators.get('rsi', 0):.1f}")
        print(f"  EMA20: ${indicators.get('ema20', 0):,.2f}")
        print(f"  EMA50: ${indicators.get('ema50', 0):,.2f}")
        print(f"  Peut entrer: {should_enter}")
        if not should_enter:
            print(f"  Raison: {reason}")
        print()

def test_very_permissive():
    """Test avec paramètres très permissifs"""
    print("="*70)
    print("🧪 TEST TRÈS PERMISSIF")
    print("="*70)
    
    try:
        import config
        config.BACKTEST_FAST_MODE = True
        original_threshold = getattr(config, 'SIGNAL_QUALITY_THRESHOLD', 82)
        original_volume = getattr(config, 'MIN_VOLUME_MULTIPLIER', 2.5)
        
        # Paramètres très permissifs
        config.SIGNAL_QUALITY_THRESHOLD = 60
        config.MIN_VOLUME_MULTIPLIER = 1.5
        config.MAX_SPREAD_PERCENT = 0.05
        
        print(f"\n📊 Paramètres très permissifs:")
        print(f"   - Signal Quality Threshold: {original_threshold} → {config.SIGNAL_QUALITY_THRESHOLD}")
        print(f"   - Volume Multiplier: {original_volume} → {config.MIN_VOLUME_MULTIPLIER}")
        print(f"   - Max Spread: {config.MAX_SPREAD_PERCENT}%")
    except Exception as e:
        print(f"⚠️  Erreur config: {e}")
    
    bt = ScalpingBacktest()
    
    print("\n⏳ Démarrage du backtest...")
    from datetime import datetime
    start_time = datetime.now()
    
    results = bt.run('BTC', signal_quality_threshold=60)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Restaurer
    try:
        import config
        config.SIGNAL_QUALITY_THRESHOLD = original_threshold
        config.MIN_VOLUME_MULTIPLIER = original_volume
    except:
        pass
    
    if 'error' not in results:
        print(f"\n✅ Backtest terminé en {duration:.1f} secondes")
        
        total_trades = results.get('total_trades', 0)
        if total_trades > 0:
            print(f"\n📊 RÉSULTATS:")
            print(f"   Total Trades: {total_trades}")
            print(f"   Winrate: {results.get('winrate', 0):.2f}%")
            print(f"   Profit Factor: {results.get('profit_factor', 0):.2f}")
            print(f"   ROI: {results.get('roi', 0):.2f}%")
            print(f"   Max Drawdown: {results.get('max_drawdown', 0):.2f}%")
        else:
            print("\n⚠️  Aucun trade généré même avec paramètres très permissifs")
            print("   Le problème vient probablement de:")
            print("   - Validation contexte (5/6 critères requis)")
            print("   - Indicateurs EMA non calculés")
            print("   - Données historiques insuffisantes")
    else:
        print(f"❌ Erreur: {results['error']}")

if __name__ == "__main__":
    print("Choisissez le test:")
    print("1. Debug signaux (analyse détaillée)")
    print("2. Test très permissif (threshold 60)")
    choice = input("\nVotre choix (1 ou 2): ")
    
    if choice == "1":
        debug_signals()
    else:
        test_very_permissive()

