"""Test simple avec tous les filtres désactivés"""
import logging

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

# IMPORTANT: Définir les flags AVANT d'importer les modules
import config
config.BACKTEST_FAST_MODE = True
config.SIGNAL_QUALITY_THRESHOLD = 60
config.SKIP_VOLUME_FILTER = True
config.SKIP_ATR_FILTER = True
config.SKIP_CONTEXT_VALIDATION = True
config.MAX_SPREAD_PERCENT = 0.1  # Très permissif

# Maintenant importer après avoir défini les flags
from backtest import ScalpingBacktest

print("🧪 TEST SIMPLE - TOUS FILTRES DÉSACTIVÉS")
print("="*70)
print(f"SKIP_VOLUME_FILTER: {getattr(config, 'SKIP_VOLUME_FILTER', False)}")
print(f"SKIP_ATR_FILTER: {getattr(config, 'SKIP_ATR_FILTER', False)}")
print(f"SKIP_CONTEXT_VALIDATION: {getattr(config, 'SKIP_CONTEXT_VALIDATION', False)}")

bt = ScalpingBacktest()
results = bt.run('BTC', signal_quality_threshold=60)

if 'error' not in results:
    print(f"\n✅ Résultats:")
    print(f"   Trades: {results.get('total_trades', 0)}")
    if results.get('total_trades', 0) > 0:
        print(f"   Winrate: {results.get('winrate', 0):.2f}%")
        print(f"   Profit Factor: {results.get('profit_factor', 0):.2f}")
        print(f"   ROI: {results.get('roi', 0):.2f}%")
    else:
        print("\n⚠️  Aucun trade généré")
        stats = results.get('debug_stats', {})
        print(f"   Signaux analysés: {stats.get('total_signals', 0)}")
        print(f"   NEUTRE: {stats.get('neutral_signals', 0)}")
        print(f"   Qualité insuffisante: {stats.get('quality_too_low', 0)}")
        print(f"   Filtres échoués: {stats.get('filters_failed', 0)}")
else:
    print(f"❌ Erreur: {results['error']}")

