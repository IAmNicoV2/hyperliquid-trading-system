"""
Configuration centralisée pour le système de trading Hyperliquid
"""

# Configuration API
API_BASE_URL = "https://api.hyperliquid.xyz/info"
WS_BASE_URL = "wss://api.hyperliquid.xyz/ws"
API_TIMEOUT = 10  # secondes
MAX_RETRIES = 3

# ============================================================================
# CONFIGURATION SCALPING CONSERVATEUR
# ============================================================================

# Configuration par défaut
DEFAULT_COIN = "BTC"
DEFAULT_INTERVAL = "5m"  # OPTIMISÉ: 5m pour moins de noise
DEFAULT_CANDLE_LIMIT = 200

# Multi-timeframe pour scalping
MULTI_TIMEFRAME = ["1m", "5m", "15m"]  # 1m signal, 5m trend, 15m contexte

# Intervalles supportés
SUPPORTED_INTERVALS = ['1m', '5m', '15m', '1h', '4h', '1d']

# ============================================================================
# INDICATEURS OPTIMISÉS (périodes plus longues)
# ============================================================================
RSI_PERIOD = 14  # Revenir à 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
EMA_SHORT = 20
EMA_LONG = 50
BOLLINGER_PERIOD = 20
BOLLINGER_STD_DEV = 2
ATR_PERIOD = 10
STOCHASTIC_PERIOD = 7
WILLIAMS_R_PERIOD = 7
CCI_PERIOD = 10

# ============================================================================
# STOP LOSS / TAKE PROFIT CONSERVATEUR
# ============================================================================
MAX_STOP_LOSS_PERCENT = 1.0  # Maximum 1% (au lieu de 0.8%)
MIN_STOP_LOSS_PERCENT = 0.6  # Minimum 0.6% (au lieu de 0.3%)
MAX_TAKE_PROFIT_PERCENT = 2.5
MIN_RISK_REWARD_RATIO = 1.5  # Ratio minimum 1.5:1

# Take Profit multi-niveaux (scalping)
TP1_PERCENT = 1.5   # Ratio 1.5:1 avec SL
TP2_PERCENT = 2.0
TP3_PERCENT = 2.5

# Trailing Stop
TRAILING_ACTIVATION = 0.8  # Activer trailing dès +0.8% profit (plus conservateur)
TRAILING_PERCENT = 50
BREAK_EVEN_ACTIVATION = 0.5  # Break-even dès +0.5%
BREAKEVEN_THRESHOLD = 0.5

# Stop Loss temporel
SL_TIME_MINUTES = 10  # Réduire à 10 min pour limiter les pertes (au lieu de 15)utes

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
# FILTRES D'ENTRÉE ULTRA-STRICTS
# ============================================================================
SIGNAL_QUALITY_THRESHOLD = 82  # Augmenter de 75 à 82
MIN_SIGNAL_CONFLUENCE = 4  # Minimum 4 indicateurs alignés
MIN_VOLUME_MULTIPLIER = 2.5  # Volume >250% moyenne 20 périodes
MAX_SPREAD_PERCENT = 0.03  # Réduire de 0.04 à 0.03
MIN_DISTANCE_SR_PERCENT = 0.3

# ATR Range acceptable (éviter extrêmes)
ATR_MIN_PERCENT = 0.5  # ATR minimum 0.5% du prix
ATR_MAX_PERCENT = 1.2  # ATR maximum 1.2% du prix

# ============================================================================
# MONEY MANAGEMENT ULTRA-CONSERVATEUR
# ============================================================================
MAX_POSITIONS = 1  # Une seule position à la fois
RISK_PER_TRADE = 0.008  # Réduire à 0.8%
MAX_DAILY_DRAWDOWN = 0.03  # Arrêter trading si drawdown journalier >3%
MAX_POSITION_HEAT = 0.05  # Heat max: 5% du capital
MAX_POSITION_SIZE_PERCENT = 0.05  # Maximum 5% du capital par position

# Ajustement dynamique de la taille
WINRATE_THRESHOLD_INCREASE = 0.60  # Augmenter taille si winrate >60% sur 20 trades
CONSECUTIVE_LOSSES_REDUCE = 3  # Réduire taille après 3 pertes consécutives

# ============================================================================
# MARKET CONDITIONS FILTERS
# ============================================================================
AVOID_TRADING_HOURS = [(22, 24), (0, 2)]  # UTC - éviter heures creuses
MIN_DAILY_VOLUME_USD = 50_000_000  # Volume min pour trader un coin
MAX_CONSECUTIVE_LOSSES = 3  # Stop après 3 pertes consécutives
COOLDOWN_AFTER_LOSS_MINUTES = 30  # Attendre 30 min après perte

# TREND FILTER
REQUIRE_TREND_ALIGNMENT = True  # Trader uniquement avec trend
MIN_TREND_STRENGTH = 0.6  # EMA20/EMA50 ratio min

# VALIDATION CONTEXTE
VALIDATION_CONTEXT_MIN_CHECKS = 4  # Réduit à 4/6 pour plus de flexibilité (au lieu de 5/6)

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
