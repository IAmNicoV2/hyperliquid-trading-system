"""
Configuration centralisée pour le système de trading Hyperliquid
"""

# Configuration API
API_BASE_URL = "https://api.hyperliquid.xyz/info"
WS_BASE_URL = "wss://api.hyperliquid.xyz/ws"
API_TIMEOUT = 10  # secondes
MAX_RETRIES = 3

# Configuration par défaut
DEFAULT_COIN = "BTC"
DEFAULT_INTERVAL = "5m"
DEFAULT_CANDLE_LIMIT = 200

# Intervalles supportés
SUPPORTED_INTERVALS = ['1m', '5m', '15m', '1h', '4h', '1d']

# Configuration des indicateurs techniques
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
EMA_SHORT = 20
EMA_LONG = 50
BOLLINGER_PERIOD = 20
BOLLINGER_STD_DEV = 2
ATR_PERIOD = 14
STOCHASTIC_PERIOD = 14
WILLIAMS_R_PERIOD = 14
CCI_PERIOD = 20

# Configuration Stop Loss / Take Profit
MAX_STOP_LOSS_PERCENT = 3.0  # Maximum 3% de perte
MAX_TAKE_PROFIT_PERCENT = 10.0  # Maximum 10% de gain
MIN_RISK_REWARD_RATIO = 1.5  # Ratio minimum Risk/Reward

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

# Configuration du backtesting (si implémenté)
BACKTEST_INITIAL_CAPITAL = 10000.0
BACKTEST_COMMISSION = 0.001  # 0.1%
BACKTEST_SLIPPAGE = 0.0005  # 0.05%
