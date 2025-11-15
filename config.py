"""
Configuration centralisée pour le système de trading Hyperliquid
"""

# Configuration API
API_BASE_URL = "https://api.hyperliquid.xyz/info"
WS_BASE_URL = "wss://api.hyperliquid.xyz/ws"
API_TIMEOUT = 10  # secondes
MAX_RETRIES = 3

# ============================================================================
# CONFIGURATION SCALPING HAUTE FRÉQUENCE
# ============================================================================

# Configuration par défaut
DEFAULT_COIN = "BTC"
DEFAULT_INTERVAL = "1m"  # SCALPING: 1 minute au lieu de 5m
DEFAULT_CANDLE_LIMIT = 200

# Multi-timeframe pour scalping
MULTI_TIMEFRAME = ["1m", "5m", "15m"]  # 1m signal, 5m trend, 15m contexte

# Intervalles supportés
SUPPORTED_INTERVALS = ['1m', '5m', '15m', '1h', '4h', '1d']

# ============================================================================
# INDICATEURS RAPIDES POUR SCALPING
# ============================================================================
RSI_PERIOD = 7  # SCALPING: 7 au lieu de 14 (plus réactif)
MACD_FAST = 8   # SCALPING: Plus rapide
MACD_SLOW = 21  # SCALPING: Plus rapide
MACD_SIGNAL = 5  # SCALPING: Plus rapide
EMA_SHORT = 9   # SCALPING: 9 au lieu de 20
EMA_LONG = 21   # SCALPING: 21 au lieu de 50
BOLLINGER_PERIOD = 20
BOLLINGER_STD_DEV = 2
ATR_PERIOD = 10  # SCALPING: 10 au lieu de 14 (plus réactif)
STOCHASTIC_PERIOD = 7  # SCALPING: Plus rapide
WILLIAMS_R_PERIOD = 7  # SCALPING: Plus rapide
CCI_PERIOD = 10  # SCALPING: Plus rapide

# ============================================================================
# STOP LOSS / TAKE PROFIT SCALPING AGRESSIF
# ============================================================================
MAX_STOP_LOSS_PERCENT = 0.8  # SCALPING: 0.3% à 0.8% (au lieu de 3%)
MIN_STOP_LOSS_PERCENT = 0.3  # Minimum SL pour scalping
MAX_TAKE_PROFIT_PERCENT = 2.5  # SCALPING: Max 2.5% (au lieu de 10%)
MIN_RISK_REWARD_RATIO = 1.2  # SCALPING: Ratio minimum 1.2 (au lieu de 1.5)

# Take Profit multi-niveaux (scalping)
TP1_PERCENT = 1.0   # 50% de la position à +1.0%
TP2_PERCENT = 1.8   # 30% de la position à +1.8%
TP3_PERCENT = 2.5   # 20% de la position à +2.5% ou résistance

# Trailing Stop
TRAILING_ACTIVATION = 0.5  # Activer trailing dès +0.5% profit
TRAILING_PERCENT = 50      # Trail à 50% du gain
BREAK_EVEN_ACTIVATION = 0.8  # Déplacer SL à break-even dès +0.8%

# Stop Loss temporel
SL_TIME_MINUTES = 10  # Fermer position si aucun profit après 10 minutes

# Configuration des frais Hyperliquid (mis à jour 2024-2025)
# Basé sur le volume de trading sur 14 jours
HYPERLIQUID_FEES = {
    'volume_tiers_14d': [
        {'level': 0, 'max_volume': 5000000, 'taker': 0.00035, 'maker': 0.0001},      # ≤ 5M USD
        {'level': 1, 'max_volume': 25000000, 'taker': 0.00030, 'maker': 0.00005},    # > 5M USD
        {'level': 2, 'max_volume': 100000000, 'taker': 0.00025, 'maker': 0.00000},   # > 25M USD
        {'level': 3, 'max_volume': 500000000, 'taker': 0.00023, 'maker': 0.00000},  # > 100M USD
        {'level': 4, 'max_volume': 2000000000, 'taker': 0.00021, 'maker': 0.00000}, # > 500M USD
        {'level': 5, 'max_volume': float('inf'), 'taker': 0.00019, 'maker': 0.00000}, # > 2B USD
    ],
    # Réductions possibles (en plus des tiers de volume)
    'referral_discount': 0.04,  # 4% de réduction avec code parrainage
    'staking_tiers': {
        'wood': {'min_hype': 10, 'discount': 0.05},      # 5% réduction
        'bronze': {'min_hype': 100, 'discount': 0.10},   # 10% réduction
        'silver': {'min_hype': 1000, 'discount': 0.15},  # 15% réduction
        'gold': {'min_hype': 10000, 'discount': 0.20},   # 20% réduction
        'platinum': {'min_hype': 100000, 'discount': 0.30},  # 30% réduction
        'diamond': {'min_hype': 500000, 'discount': 0.40},   # 40% réduction
    }
}

# Fonction helper pour obtenir les frais selon le volume 14 jours
def get_hyperliquid_fees_by_volume(volume_14d: float = 0, use_referral: bool = False, staking_tier: str = None):
    """Retourne les frais selon le volume 14 jours"""
    tiers = HYPERLIQUID_FEES['volume_tiers_14d']
    
    # Trouver le tier approprié
    for tier in tiers:
        if volume_14d <= tier['max_volume']:
            maker_fee = tier['maker']
            taker_fee = tier['taker']
            break
    else:
        # Par défaut, utiliser le dernier tier
        maker_fee = tiers[-1]['maker']
        taker_fee = tiers[-1]['taker']
    
    # Appliquer réductions
    discount = 0.0
    if use_referral:
        discount += HYPERLIQUID_FEES['referral_discount']
    if staking_tier and staking_tier in HYPERLIQUID_FEES['staking_tiers']:
        discount += HYPERLIQUID_FEES['staking_tiers'][staking_tier]['discount']
    
    discount = min(discount, 0.44)  # Max 44%
    
    return {
        'maker': maker_fee * (1 - discount),
        'taker': taker_fee * (1 - discount),
        'maker_percent': (maker_fee * (1 - discount)) * 100,
        'taker_percent': (taker_fee * (1 - discount)) * 100,
        'base_maker': maker_fee,
        'base_taker': taker_fee,
        'discount_percent': discount * 100
    }

# Configuration du compte (à remplir avec les clés API)
HYPERLIQUID_API = {
    'wallet_address': '',  # Adresse wallet
    'private_key': '',      # Clé privée (sera chargée depuis variable d'environnement)
    'use_referral': False,  # Utiliser code parrainage
    'referral_code': '',    # Code parrainage si applicable
    'staking_tier': None,   # Tier de staking HYPE (wood, bronze, silver, gold, platinum, diamond)
    'volume_14d': 0.0,     # Volume 14 jours pour calcul frais (utilisé par Hyperliquid)
    'volume_30d': 0.0,     # Volume 30 jours (optionnel, pour référence)
}

# Configuration du serveur web
WEB_SERVER_HOST = '0.0.0.0'
WEB_SERVER_PORT = 5000
WEB_UPDATE_INTERVAL = 5  # secondes
MONITORING_INTERVAL = 30  # secondes

# Configuration du logging
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Seuils de signaux
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
RSI_NEUTRAL_LOW = 40
RSI_NEUTRAL_HIGH = 60

STOCHASTIC_OVERSOLD = 20
STOCHASTIC_OVERBOUGHT = 80

WILLIAMS_R_OVERSOLD = -80
WILLIAMS_R_OVERBOUGHT = -20

CCI_OVERSOLD = -100
CCI_OVERBOUGHT = 100

ORDER_FLOW_THRESHOLD = 10  # Pourcentage de déséquilibre significatif

# Configuration de l'analyse avancée
VOLATILITY_LOW_THRESHOLD = 0.3  # %
VOLATILITY_HIGH_THRESHOLD = 0.8  # %
SQUEEZE_THRESHOLD = 0.5  # Multiplicateur pour détecter le squeeze

WALL_DETECTION_MULTIPLIER = 1.5  # Mur = 1.5x la moyenne
WALL_DISTANCE_THRESHOLD = 0.01  # 1% du prix pour être considéré comme "proche"

# ============================================================================
# FILTRES D'ENTRÉE SCALPING
# ============================================================================
MIN_VOLUME_MULTIPLIER = 1.5  # Volume >150% moyenne 20 périodes
MAX_SPREAD_PERCENT = 0.05  # Spread max 0.05% (éviter trades si spread trop élevé)
MIN_DISTANCE_SR_PERCENT = 0.3  # Distance minimum du dernier S/R: 0.3%
SIGNAL_QUALITY_THRESHOLD = 70  # Score qualité minimum pour entrer (0-100)

# ATR Range acceptable pour scalping
ATR_MIN_PERCENT = 0.4  # ATR minimum 0.4% du prix
ATR_MAX_PERCENT = 1.2  # ATR maximum 1.2% du prix

# ============================================================================
# MONEY MANAGEMENT SCALPING
# ============================================================================
MAX_POSITIONS = 3  # Maximum 3 positions simultanées
RISK_PER_TRADE = 0.015  # 1.5% du capital par trade (Kelly Criterion adapté)
MAX_DAILY_DRAWDOWN = 0.05  # Arrêter trading si drawdown journalier >5%
MAX_POSITION_HEAT = 0.08  # Heat max: 8% du capital (nb positions * risk)

# Ajustement dynamique de la taille
WINRATE_THRESHOLD_INCREASE = 0.60  # Augmenter taille si winrate >60% sur 20 trades
CONSECUTIVE_LOSSES_REDUCE = 3  # Réduire taille après 3 pertes consécutives

# ============================================================================
# ORDER BOOK PROFOND
# ============================================================================
ORDERBOOK_DEPTH = 50  # Top 50 niveaux (au lieu de 20)
ORDERBOOK_IMBALANCE_LEVELS = 10  # Calculer imbalance sur 10 premiers niveaux
ICEBERG_DETECTION = True  # Détecter les iceberg orders

# ============================================================================
# OPTIMISATION FRAIS (MAKER vs TAKER)
# ============================================================================
PREFER_MAKER_ORDERS = True  # Privilégier LIMIT orders (maker rebate)
MAKER_OFFSET_PERCENT = 0.01  # Placer orders 0.01% below/above pour être maker
ORDER_TIMEOUT_SECONDS = 2  # Cancel & replace si pas fill en 2 secondes

# ============================================================================
# BACKTESTING ENGINE
# ============================================================================
BACKTEST_INITIAL_CAPITAL = 10000.0
BACKTEST_COMMISSION_TAKER = 0.00035  # 0.035% (frais réels Hyperliquid)
BACKTEST_COMMISSION_MAKER = 0.0001   # 0.01% (frais réels Hyperliquid)
BACKTEST_SLIPPAGE = 0.0002  # 0.02% par trade (scalping)
BACKTEST_LATENCY_MS = 100  # Latence simulée 50-150ms (moyenne 100ms)
BACKTEST_MIN_DAYS = 30  # Minimum 30 jours de données historiques

# Métriques cibles backtest
TARGET_WINRATE = 0.55  # Winrate cible >55%
TARGET_PROFIT_FACTOR = 1.3  # Profit factor cible >1.3
TARGET_MAX_DRAWDOWN = 0.12  # Max drawdown cible <12%
