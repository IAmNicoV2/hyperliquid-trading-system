"""
Analyse la distribution des qualités de signal pour optimiser le seuil
"""

import logging
from collections import defaultdict
from hyperliquid_signals import HyperliquidSignalGenerator
from backtest import ScalpingBacktest
import config

logging.basicConfig(level=logging.WARNING)  # Réduire les logs
logger = logging.getLogger(__name__)

def analyze_signal_quality_distribution(coin: str = 'BTC', days: int = 7):
    """Analyse la distribution des qualités de signal"""
    
    print(f"\n{'='*80}")
    print(f"📊 ANALYSE DISTRIBUTION QUALITÉ SIGNAL - {coin}")
    print(f"{'='*80}\n")
    
    # Charger les données
    backtest = ScalpingBacktest(initial_capital=10000)
    candles = backtest.load_historical_data(coin, interval=config.DEFAULT_INTERVAL, days=days)
    
    if not candles or len(candles) < 100:
        print(f"❌ Pas assez de données pour {coin}")
        return
    
    print(f"✅ {len(candles)} chandeliers chargés\n")
    
    # Initialiser le générateur
    signal_generator = HyperliquidSignalGenerator(coin=coin, interval=config.DEFAULT_INTERVAL)
    
    # Analyser tous les signaux
    quality_scores = []
    signal_types = defaultdict(int)
    quality_by_signal = defaultdict(list)
    
    start_index = 100
    for i in range(start_index, len(candles)):
        candle = candles[i]
        signal_generator.candles = candles[:i+1]
        signal_generator.current_price = candle['close']
        
        try:
            analysis = signal_generator.analyze()
            
            if 'error' in analysis:
                continue
            
            signal = analysis.get('signal', 'NEUTRE')
            signal_quality = analysis.get('signal_quality', 0)
            
            if signal != 'NEUTRE' and signal_quality > 0:
                quality_scores.append(signal_quality)
                signal_types[signal] += 1
                quality_by_signal[signal].append(signal_quality)
        
        except Exception as e:
            continue
    
    if not quality_scores:
        print("❌ Aucun signal avec qualité > 0 trouvé")
        return
    
    # Statistiques
    quality_scores.sort()
    total = len(quality_scores)
    
    print(f"📈 STATISTIQUES QUALITÉ SIGNAL:")
    print(f"  Total signaux ACHAT/VENTE: {total}")
    print(f"  Signaux ACHAT: {signal_types.get('ACHAT', 0)}")
    print(f"  Signaux VENTE: {signal_types.get('VENTE', 0)}")
    print(f"\n  Qualité moyenne: {sum(quality_scores)/total:.2f}")
    print(f"  Qualité médiane: {quality_scores[total//2]:.2f}")
    print(f"  Qualité min: {min(quality_scores):.2f}")
    print(f"  Qualité max: {max(quality_scores):.2f}")
    
    # Distribution par seuils
    print(f"\n📊 DISTRIBUTION PAR SEUILS:")
    thresholds = [60, 65, 70, 72, 75, 78, 80, 85]
    for threshold in thresholds:
        count = sum(1 for q in quality_scores if q >= threshold)
        percentage = (count / total) * 100
        print(f"  Qualité >= {threshold:2d}: {count:5d} signaux ({percentage:5.1f}%)")
    
    # Percentiles
    print(f"\n📊 PERCENTILES:")
    percentiles = [10, 25, 50, 75, 90, 95, 99]
    for p in percentiles:
        index = int(total * p / 100)
        if index < total:
            print(f"  {p:2d}ème percentile: {quality_scores[index]:.2f}")
    
    # Recommandation
    current_threshold = getattr(config, 'SIGNAL_QUALITY_THRESHOLD', 78)
    signals_above_current = sum(1 for q in quality_scores if q >= current_threshold)
    percentage_above = (signals_above_current / total) * 100
    
    print(f"\n💡 ANALYSE:")
    print(f"  Seuil actuel: {current_threshold}")
    print(f"  Signaux >= seuil actuel: {signals_above_current} ({percentage_above:.1f}%)")
    
    # Recommandations
    print(f"\n🎯 RECOMMANDATIONS:")
    
    # Seuil pour avoir ~10-15% de signaux
    target_percentage = 12
    target_count = int(total * target_percentage / 100)
    if target_count > 0 and target_count < total:
        recommended_threshold = quality_scores[-target_count] if target_count < len(quality_scores) else quality_scores[0]
        print(f"  Pour avoir ~{target_percentage}% de signaux: seuil = {recommended_threshold:.1f}")
    
    # Seuil pour avoir ~20% de signaux
    target_percentage = 20
    target_count = int(total * target_percentage / 100)
    if target_count > 0 and target_count < total:
        recommended_threshold = quality_scores[-target_count] if target_count < len(quality_scores) else quality_scores[0]
        print(f"  Pour avoir ~{target_percentage}% de signaux: seuil = {recommended_threshold:.1f}")
    
    # Seuil optimal basé sur le 75ème percentile
    percentile_75 = quality_scores[int(total * 0.75)]
    print(f"  Seuil basé sur 75ème percentile: {percentile_75:.1f}")
    
    # Seuil optimal basé sur la médiane + écart-type
    import statistics
    if len(quality_scores) > 1:
        mean_quality = statistics.mean(quality_scores)
        std_quality = statistics.stdev(quality_scores)
        recommended_std = mean_quality + 0.5 * std_quality
        print(f"  Seuil basé sur moyenne + 0.5*écart-type: {recommended_std:.1f}")
    
    print(f"\n{'='*80}\n")

if __name__ == '__main__':
    # Analyser pour tous les coins
    supported_coins = getattr(config, 'SUPPORTED_COINS', ['BTC', 'ETH', 'SOL', 'HYPE', 'ARB'])
    
    for coin in supported_coins:
        try:
            analyze_signal_quality_distribution(coin, days=7)
        except Exception as e:
            print(f"❌ Erreur pour {coin}: {e}\n")

