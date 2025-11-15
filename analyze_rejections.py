"""
Script d'analyse des rejets pour identifier les problèmes de la stratégie
"""

import logging
from collections import defaultdict
from backtest_strategy import run_strategy_backtest
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_all_rejections():
    """Analyse les rejets pour tous les coins"""
    supported_coins = getattr(config, 'SUPPORTED_COINS', ['BTC', 'ETH', 'SOL', 'HYPE', 'ARB'])
    
    all_rejections = defaultdict(int)
    all_neutral = 0
    all_signals = 0
    
    for coin in supported_coins:
        print(f"\n{'='*80}")
        print(f"Analyse des rejets pour {coin}")
        print(f"{'='*80}")
        
        result = run_strategy_backtest(coin, days=7)
        
        # Collecter les statistiques globales
        # (Les stats sont déjà affichées dans run_strategy_backtest)
    
    print(f"\n{'='*80}")
    print("RECOMMANDATIONS GLOBALES")
    print(f"{'='*80}")
    print("""
    Basé sur l'analyse des rejets, voici les ajustements recommandés :
    
    1. Si 'signal_quality' est le rejet principal :
       → Réduire SIGNAL_QUALITY_THRESHOLD de 78 à 72-75
    
    2. Si 'confluence_buy_signals' ou 'confluence_sell_signals' :
       → Réduire min_buy_signals/min_sell_signals de 4 à 3
       → Réduire signal_dominance de 2 à 1
    
    3. Si 'volume' est fréquent :
       → Réduire MIN_VOLUME_MULTIPLIER de 2.2 à 1.8-2.0
    
    4. Si 'spread' est fréquent :
       → Augmenter MAX_SPREAD_PERCENT de 0.03% à 0.05%
    
    5. Si 'atr' est fréquent :
       → Ajuster ATR_MIN_PERCENT et ATR_MAX_PERCENT
       → Ou désactiver temporairement le filtre ATR
    
    6. Si 'confidence' est fréquent :
       → Réduire le min_confidence de 60 à 50-55
    """)

if __name__ == '__main__':
    analyze_all_rejections()

