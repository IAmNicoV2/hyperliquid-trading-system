"""
Système de génération de signaux de trading Hyperliquid
Basé sur l'analyse technique avancée avec RSI, MACD, EMA, Bollinger Bands
"""

import sys
import io

# Configuration de l'encodage UTF-8 pour Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import websocket
import threading
from functools import lru_cache
import logging

# Tentative d'importer la configuration, sinon utiliser les valeurs par défaut
try:
    import config
    API_TIMEOUT = getattr(config, 'API_TIMEOUT', 10)
    MAX_RETRIES = getattr(config, 'MAX_RETRIES', 3)
    DEFAULT_COIN = getattr(config, 'DEFAULT_COIN', 'BTC')
    DEFAULT_INTERVAL = getattr(config, 'DEFAULT_INTERVAL', '5m')
    LOG_LEVEL = getattr(config, 'LOG_LEVEL', 'INFO')
except ImportError:
    API_TIMEOUT = 10
    MAX_RETRIES = 3
    DEFAULT_COIN = 'BTC'
    DEFAULT_INTERVAL = '5m'
    LOG_LEVEL = 'INFO'

# Configuration du logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HyperliquidSignalGenerator:
    def __init__(self, coin: str = None, interval: str = None, timeout: int = None, max_retries: int = None):
        self.coin = coin or DEFAULT_COIN
        self.interval = interval or DEFAULT_INTERVAL
        self.api_url = "https://api.hyperliquid.xyz/info"
        self.ws_url = "wss://api.hyperliquid.xyz/ws"
        self.candles = []
        self.current_price = 0
        self.order_book = {"bids": [], "asks": []}
        self.price_history = []  # Pour l'analyse de micro-structure
        self.volume_history = []  # Pour l'analyse de volume
        self.timeout = timeout or API_TIMEOUT
        self.max_retries = max_retries or MAX_RETRIES
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'HyperliquidSignalGenerator/1.0'
        })
        
    def get_interval_ms(self, interval: str) -> int:
        """Convertit l'intervalle en millisecondes"""
        intervals = {
            '1m': 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '4h': 4 * 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000
        }
        return intervals.get(interval, 60 * 1000)
    
    def fetch_historical_candles(self, limit: int = 200) -> List[Dict]:
        """Récupère les chandeliers historiques avec retry logic"""
        for attempt in range(self.max_retries):
            try:
                response = self.session.post(
                    self.api_url,
                    json={
                        'type': 'candleSnapshot',
                        'req': {
                            'coin': self.coin,
                            'interval': self.interval,
                            'startTime': int(time.time() * 1000) - (limit * self.get_interval_ms(self.interval)),
                            'endTime': int(time.time() * 1000)
                        }
                    },
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0:
                        candles = []
                        for candle in data:
                            try:
                                candles.append({
                                    'time': int(candle['t'] / 1000),
                                    'open': float(candle['o']),
                                    'high': float(candle['h']),
                                    'low': float(candle['l']),
                                    'close': float(candle['c']),
                                    'volume': float(candle.get('v', 0))
                                })
                            except (KeyError, ValueError, TypeError) as e:
                                logger.warning(f"Chandelier invalide ignoré: {e}")
                                continue
                        
                        if candles:
                            self.candles = candles
                            self.current_price = candles[-1]['close']
                            logger.info(f"✅ {len(candles)} chandeliers récupérés pour {self.coin}")
                            return candles
                    else:
                        logger.warning(f"Réponse API vide ou invalide: {type(data)}")
                        
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout lors de la récupération (tentative {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(1 * (attempt + 1))  # Backoff exponentiel
            except requests.exceptions.RequestException as e:
                logger.error(f"Erreur réseau lors de la récupération des chandeliers: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1 * (attempt + 1))
            except Exception as e:
                logger.error(f"Erreur inattendue lors de la récupération des chandeliers: {e}", exc_info=True)
                if attempt < self.max_retries - 1:
                    time.sleep(1 * (attempt + 1))
        
        logger.error(f"❌ Impossible de récupérer les chandeliers après {self.max_retries} tentatives")
        return []
    
    def fetch_order_book(self) -> Dict:
        """Récupère le carnet d'ordres depuis l'API Hyperliquid avec retry logic"""
        for attempt in range(self.max_retries):
            try:
                response = self.session.post(
                    self.api_url,
                    json={
                        'type': 'l2Book',
                        'coin': self.coin
                    },
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                
                if response.status_code == 200:
                    data = response.json()
                    if data and 'levels' in data and len(data['levels']) == 2:
                        bids = data['levels'][0] if isinstance(data['levels'][0], list) else []
                        asks = data['levels'][1] if isinstance(data['levels'][1], list) else []
                        self.order_book = {'bids': bids, 'asks': asks}
                        logger.debug(f"Order book récupéré: {len(bids)} bids, {len(asks)} asks")
                        return self.order_book
                    else:
                        logger.warning("Format de réponse order book invalide")
                        
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout lors de la récupération de l'order book (tentative {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
            except requests.exceptions.RequestException as e:
                logger.error(f"Erreur réseau lors de la récupération de l'order book: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
            except Exception as e:
                logger.error(f"Erreur inattendue lors de la récupération de l'order book: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
        
        logger.warning(f"Impossible de récupérer l'order book après {self.max_retries} tentatives")
        return {'bids': [], 'asks': []}
    
    def get_hyperliquid_fees(self, volume_14d: float = 0, use_referral: bool = False, staking_tier: str = None) -> Dict[str, float]:
        """Récupère les frais Hyperliquid (maker/taker) avec réductions possibles basé sur volume 14 jours"""
        try:
            import config
            # Utiliser la fonction helper si disponible
            if hasattr(config, 'get_hyperliquid_fees_by_volume'):
                return config.get_hyperliquid_fees_by_volume(volume_14d, use_referral, staking_tier)
            
            # Sinon, utiliser l'ancienne méthode
            fees_config = config.HYPERLIQUID_FEES
            tiers = fees_config.get('volume_tiers_14d', [])
            
            # Trouver le tier approprié
            maker_fee = 0.0001  # Par défaut
            taker_fee = 0.00035  # Par défaut
            
            for tier in tiers:
                if volume_14d <= tier.get('max_volume', float('inf')):
                    maker_fee = tier.get('maker', 0.0001)
                    taker_fee = tier.get('taker', 0.00035)
                    break
        except ImportError:
            # Valeurs par défaut si config non disponible
            maker_fee = 0.0001
            taker_fee = 0.00035
            fees_config = {'referral_discount': 0.04, 'staking_tiers': {}}
        
        # Appliquer réduction parrainage (4%)
        discount = 0.0
        if use_referral:
            discount += fees_config.get('referral_discount', 0.04)
        
        # Appliquer réduction staking HYPE
        if staking_tier and staking_tier in fees_config.get('staking_tiers', {}):
            staking_discount = fees_config['staking_tiers'][staking_tier].get('discount', 0)
            discount += staking_discount
        
        # Limiter la réduction totale à 44% (4% parrainage + 40% diamond max)
        discount = min(discount, 0.44)
        
        # Appliquer les réductions
        maker_fee_effective = maker_fee * (1 - discount)
        taker_fee_effective = taker_fee * (1 - discount)
        
        return {
            'maker': maker_fee_effective,
            'taker': taker_fee_effective,
            'maker_percent': maker_fee_effective * 100,
            'taker_percent': taker_fee_effective * 100,
            'base_maker': maker_fee,
            'base_taker': taker_fee,
            'discount_percent': discount * 100,
            'effective_maker_percent': maker_fee_effective * 100,
            'effective_taker_percent': taker_fee_effective * 100
        }
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calcule le RSI (Relative Strength Index) avec méthode Wilder (plus précise)"""
        if len(prices) < period + 1:
            return 50.0
        
        # Calcul initial de la moyenne des gains et pertes
        changes = [prices[i] - prices[i - 1] for i in range(len(prices) - period, len(prices))]
        gains = [c if c > 0 else 0 for c in changes]
        losses = [-c if c < 0 else 0 for c in changes]
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        # Méthode de Wilder : moyenne mobile exponentielle
        for i in range(len(prices) - period + 1, len(prices)):
            change = prices[i] - prices[i - 1]
            gain = change if change > 0 else 0
            loss = -change if change < 0 else 0
            
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return max(0, min(100, rsi))  # Clamp entre 0 et 100
    
    def calculate_ema(self, prices: List[float], period: int) -> float:
        """Calcule l'EMA (Exponential Moving Average) avec validation"""
        if len(prices) < period:
            return prices[-1] if prices else 0.0
        
        if period <= 0:
            return prices[-1] if prices else 0.0
        
        # Utiliser SMA comme point de départ pour plus de précision
        multiplier = 2.0 / (period + 1.0)
        ema = sum(prices[:period]) / float(period)
        
        # Calculer l'EMA sur les prix restants
        for i in range(period, len(prices)):
            ema = (prices[i] * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def calculate_macd(self, prices: List[float]) -> Dict[str, float]:
        """
        Calcule le MACD (Moving Average Convergence Divergence) - OPTIMISÉ
        Utilise un calcul incrémental pour éviter O(n²)
        """
        try:
            import config
            macd_fast = getattr(config, 'MACD_FAST', 8)
            macd_slow = getattr(config, 'MACD_SLOW', 21)
            macd_signal = getattr(config, 'MACD_SIGNAL', 5)
        except:
            macd_fast = 8
            macd_slow = 21
            macd_signal = 5
        
        if len(prices) < macd_slow:
            return {'value': 0, 'signal': 0, 'histogram': 0}
        
        # Calcul EMA rapide et lente de manière optimisée
        ema_fast = self.calculate_ema(prices, macd_fast)
        ema_slow = self.calculate_ema(prices, macd_slow)
        macd_line = ema_fast - ema_slow
        
        # Calcul de la ligne de signal (EMA du MACD) - OPTIMISÉ
        # Calculer les valeurs MACD de manière incrémentale
        macd_values = []
        
        # Calculer EMA fast et slow pour chaque point (de manière optimisée)
        if len(prices) >= macd_slow:
            # Utiliser une approche plus efficace : calculer seulement les dernières valeurs nécessaires
            # Pour la ligne de signal, on a besoin des valeurs MACD depuis macd_slow jusqu'à la fin
            # Mais on peut simplifier en calculant seulement les dernières valeurs
            
            # Calculer MACD pour les dernières N périodes (assez pour EMA signal)
            # On a besoin d'au moins macd_signal valeurs MACD pour calculer l'EMA signal
            start_idx = max(macd_slow, len(prices) - 50)  # Calculer seulement les 50 dernières si possible
            
            for i in range(start_idx, len(prices)):
                # Calculer EMA fast et slow pour cette position
                ema_fast_i = self.calculate_ema(prices[:i+1], macd_fast)
                ema_slow_i = self.calculate_ema(prices[:i+1], macd_slow)
                macd_values.append(ema_fast_i - ema_slow_i)
            
            # Si on n'a pas assez de valeurs, calculer depuis macd_slow
            if len(macd_values) < macd_signal:
                macd_values = []
                for i in range(macd_slow, len(prices)):
                    ema_fast_i = self.calculate_ema(prices[:i+1], macd_fast)
                    ema_slow_i = self.calculate_ema(prices[:i+1], macd_slow)
                    macd_values.append(ema_fast_i - ema_slow_i)
        
        # Calculer la ligne de signal (EMA du MACD)
        if len(macd_values) >= macd_signal:
            signal_line = self.calculate_ema(macd_values, macd_signal)
        else:
            # Si pas assez de valeurs, utiliser une approximation
            signal_line = macd_line * 0.8  # Approximation
            # Ou calculer avec les valeurs disponibles
            if len(macd_values) > 0:
                signal_line = sum(macd_values) / len(macd_values)
            else:
                signal_line = 0
        
        histogram = macd_line - signal_line
        
        return {
            'value': round(macd_line, 4),
            'signal': round(signal_line, 4),
            'histogram': round(histogram, 4)
        }
    
    def calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: int = 2) -> Dict[str, float]:
        """Calcule les Bandes de Bollinger avec validation"""
        if len(prices) < period:
            current_price = prices[-1] if prices else 0.0
            return {'upper': current_price, 'middle': current_price, 'lower': current_price}
        
        recent_prices = prices[-period:]
        middle = sum(recent_prices) / float(period)
        
        # Calcul de l'écart-type avec correction de Bessel (n-1)
        variance = sum((p - middle) ** 2 for p in recent_prices) / float(period - 1) if period > 1 else 0.0
        std = variance ** 0.5
        
        return {
            'upper': middle + (std_dev * std),
            'middle': middle,
            'lower': max(0, middle - (std_dev * std))  # Éviter les valeurs négatives
        }
    
    def calculate_volume_profile(self, candles: List[Dict]) -> Dict[str, float]:
        """Calcule le Volume Profile (POC, VAH, VAL)"""
        if len(candles) < 20:
            return {'poc': 0, 'vah': 0, 'val': 0}
        
        recent_candles = candles[-50:]
        price_volumes = {}
        
        for candle in recent_candles:
            price = round(candle['close'])
            price_volumes[price] = price_volumes.get(price, 0) + candle.get('volume', 0)
        
        sorted_prices = sorted(price_volumes.items(), key=lambda x: x[1], reverse=True)
        
        if not sorted_prices:
            return {'poc': 0, 'vah': 0, 'val': 0}
        
        poc = float(sorted_prices[0][0])
        total_volume = sum(price_volumes.values())
        value_area = total_volume * 0.7
        
        cum_volume = 0
        vah_idx = 0
        for i, (_, vol) in enumerate(sorted_prices):
            cum_volume += vol
            if cum_volume >= value_area:
                vah_idx = i
                break
        
        vah_prices = [float(p) for p, _ in sorted_prices[:vah_idx + 1]]
        vah = max(vah_prices) if vah_prices else poc
        val = min(vah_prices) if vah_prices else poc
        
        return {'poc': poc, 'vah': vah, 'val': val}
    
    def calculate_order_flow_imbalance(self, bids: List[Dict], asks: List[Dict], levels: int = None) -> float:
        """Calcule le déséquilibre du flux d'ordres sur N niveaux"""
        if not bids or not asks:
            return 0.0
        
        # Utiliser la config ou valeur par défaut
        if levels is None:
            try:
                import config
                levels = getattr(config, 'ORDERBOOK_IMBALANCE_LEVELS', 10)
            except:
                levels = 10
        
        bid_volume = sum(float(b.get('sz', b.get('size', b.get('s', 0)))) if isinstance(b, dict) else float(b[1] if isinstance(b, (list, tuple)) and len(b) >= 2 else 0) for b in bids[:levels])
        ask_volume = sum(float(a.get('sz', a.get('size', a.get('s', 0)))) if isinstance(a, dict) else float(a[1] if isinstance(a, (list, tuple)) and len(a) >= 2 else 0) for a in asks[:levels])
        
        total_volume = bid_volume + ask_volume
        if total_volume == 0:
            return 0.0
        
        imbalance = ((bid_volume - ask_volume) / total_volume) * 100
        return imbalance
    
    def analyze_order_book_depth(self, bids: List[Dict], asks: List[Dict], price: float) -> Dict:
        """
        Analyse approfondie du carnet d'ordres (50 niveaux) pour scalping
        Détecte: murs, iceberg orders, liquidité, spread
        """
        if not bids or not asks:
            return {
                'support_levels': [],
                'resistance_levels': [],
                'liquidity_zones': [],
                'order_book_imbalance': 0,
                'wall_detected': False,
                'wall_price': 0,
                'wall_side': None,
                'spread_percent': 0,
                'bid_ask_ratio': 0,
                'liquidity_depth': 0,
                'iceberg_detected': False
            }
        
        # Profondeur configurable (50 niveaux pour scalping)
        try:
            import config
            depth = getattr(config, 'ORDERBOOK_DEPTH', 50)
        except:
            depth = 50
        
        # Calculer le spread
        best_bid = float(bids[0][0] if isinstance(bids[0], (list, tuple)) else bids[0].get('px', bids[0].get('price', bids[0].get('p', 0))))
        best_ask = float(asks[0][0] if isinstance(asks[0], (list, tuple)) else asks[0].get('px', asks[0].get('price', asks[0].get('p', 0))))
        spread_abs = best_ask - best_bid
        spread_percent = (spread_abs / best_bid * 100) if best_bid > 0 else 0
        
        # Analyser les murs d'ordres (walls) - 50 niveaux
        bid_walls = []
        ask_walls = []
        
        # Identifier les murs dans les bids (support)
        for i, bid in enumerate(bids[:depth]):
            # Gérer différents formats de données
            if isinstance(bid, dict):
                size = float(bid.get('sz', bid.get('size', bid.get('s', 0))))
                price_level = float(bid.get('px', bid.get('price', bid.get('p', 0))))
            elif isinstance(bid, (list, tuple)) and len(bid) >= 2:
                # Format [price, size] ou [price, size, ...]
                price_level = float(bid[0])
                size = float(bid[1])
            else:
                continue
                
            if size > 0 and price_level > 0:
                # Mur significatif : volume > 2x la moyenne des 5 niveaux précédents
                if i > 0:
                    prev_bids = bids[max(0, i-5):i]
                    prev_sizes = []
                    for prev_bid in prev_bids:
                        if isinstance(prev_bid, dict):
                            prev_sizes.append(float(prev_bid.get('sz', prev_bid.get('size', prev_bid.get('s', 0)))))
                        elif isinstance(prev_bid, (list, tuple)) and len(prev_bid) >= 2:
                            prev_sizes.append(float(prev_bid[1]))
                    avg_size = sum(prev_sizes) / len(prev_sizes) if prev_sizes else size
                else:
                    avg_size = size
                    
                if size > avg_size * 1.5 and size > 0.01:  # Seuil abaissé pour plus de détection
                    bid_walls.append({'price': price_level, 'size': size, 'distance': price - price_level})
        
        # Identifier les murs dans les asks (résistance)
        for i, ask in enumerate(asks[:20]):
            # Gérer différents formats de données
            if isinstance(ask, dict):
                size = float(ask.get('sz', ask.get('size', ask.get('s', 0))))
                price_level = float(ask.get('px', ask.get('price', ask.get('p', 0))))
            elif isinstance(ask, (list, tuple)) and len(ask) >= 2:
                # Format [price, size] ou [price, size, ...]
                price_level = float(ask[0])
                size = float(ask[1])
            else:
                continue
                
            if size > 0 and price_level > 0:
                if i > 0:
                    prev_asks = asks[max(0, i-5):i]
                    prev_sizes = []
                    for prev_ask in prev_asks:
                        if isinstance(prev_ask, dict):
                            prev_sizes.append(float(prev_ask.get('sz', prev_ask.get('size', prev_ask.get('s', 0)))))
                        elif isinstance(prev_ask, (list, tuple)) and len(prev_ask) >= 2:
                            prev_sizes.append(float(prev_ask[1]))
                    avg_size = sum(prev_sizes) / len(prev_sizes) if prev_sizes else size
                else:
                    avg_size = size
                    
                if size > avg_size * 1.5 and size > 0.01:  # Seuil abaissé
                    ask_walls.append({'price': price_level, 'size': size, 'distance': price_level - price})
        
        # Identifier le mur le plus proche et significatif
        closest_wall = None
        wall_side = None
        if bid_walls:
            closest_bid_wall = min(bid_walls, key=lambda x: x['distance'])
            if closest_bid_wall['distance'] < price * 0.01:  # Moins de 1% du prix
                closest_wall = closest_bid_wall
                wall_side = 'support'
        
        if ask_walls:
            closest_ask_wall = min(ask_walls, key=lambda x: x['distance'])
            if closest_ask_wall['distance'] < price * 0.01:
                if not closest_wall or closest_ask_wall['distance'] < closest_wall['distance']:
                    closest_wall = closest_ask_wall
                    wall_side = 'resistance'
        
        # Zones de liquidité (clusters d'ordres)
        liquidity_zones = []
        price_clusters = {}
        
        for bid in bids[:15]:
            if isinstance(bid, dict):
                p = round(float(bid.get('px', bid.get('price', bid.get('p', 0)))), -1)
                sz = float(bid.get('sz', bid.get('size', bid.get('s', 0))))
            elif isinstance(bid, (list, tuple)) and len(bid) >= 2:
                p = round(float(bid[0]), -1)
                sz = float(bid[1])
            else:
                continue
            if p > 0:
                price_clusters[p] = price_clusters.get(p, 0) + sz
        
        for ask in asks[:15]:
            if isinstance(ask, dict):
                p = round(float(ask.get('px', ask.get('price', ask.get('p', 0)))), -1)
                sz = float(ask.get('sz', ask.get('size', ask.get('s', 0))))
            elif isinstance(ask, (list, tuple)) and len(ask) >= 2:
                p = round(float(ask[0]), -1)
                sz = float(ask[1])
            else:
                continue
            if p > 0:
                price_clusters[p] = price_clusters.get(p, 0) + sz
        
        # Identifier les zones avec forte liquidité
        if price_clusters:
            avg_liquidity = sum(price_clusters.values()) / len(price_clusters)
            for p, liq in price_clusters.items():
                if liq > avg_liquidity * 1.5:
                    liquidity_zones.append({'price': p, 'liquidity': liq})
        
        # Niveaux de support (top 3 bids les plus volumineux)
        support_levels = sorted(bid_walls, key=lambda x: x['size'], reverse=True)[:3]
        
        # Niveaux de résistance (top 3 asks les plus volumineux)
        resistance_levels = sorted(ask_walls, key=lambda x: x['size'], reverse=True)[:3]
        
        # Déséquilibre du carnet d'ordres sur N niveaux
        try:
            import config
            imbalance_levels = getattr(config, 'ORDERBOOK_IMBALANCE_LEVELS', 10)
        except:
            imbalance_levels = 10
        
        total_bid_vol = 0
        for b in bids[:imbalance_levels]:
            if isinstance(b, dict):
                total_bid_vol += float(b.get('sz', b.get('size', b.get('s', 0))))
            elif isinstance(b, (list, tuple)) and len(b) >= 2:
                total_bid_vol += float(b[1])
        
        total_ask_vol = 0
        for a in asks[:imbalance_levels]:
            if isinstance(a, dict):
                total_ask_vol += float(a.get('sz', a.get('size', a.get('s', 0))))
            elif isinstance(a, (list, tuple)) and len(a) >= 2:
                total_ask_vol += float(a[1])
        
        total_vol = total_bid_vol + total_ask_vol
        imbalance = ((total_bid_vol - total_ask_vol) / total_vol * 100) if total_vol > 0 else 0
        
        # Bid/Ask Ratio
        bid_ask_ratio = total_bid_vol / total_ask_vol if total_ask_vol > 0 else 1.0
        
        # Liquidity Depth (volume total sur 50 niveaux)
        liquidity_depth = total_vol
        
        # Détection d'Iceberg Orders (volumes cachés)
        # Un iceberg se caractérise par: volume constant à plusieurs niveaux consécutifs
        iceberg_detected = False
        try:
            import config
            if getattr(config, 'ICEBERG_DETECTION', True):
                # Analyser les 20 premiers niveaux
                bid_sizes = []
                ask_sizes = []
                
                for b in bids[:20]:
                    if isinstance(b, dict):
                        bid_sizes.append(float(b.get('sz', b.get('size', b.get('s', 0)))))
                    elif isinstance(b, (list, tuple)) and len(b) >= 2:
                        bid_sizes.append(float(b[1]))
                
                for a in asks[:20]:
                    if isinstance(a, dict):
                        ask_sizes.append(float(a.get('sz', a.get('size', a.get('s', 0)))))
                    elif isinstance(a, (list, tuple)) and len(a) >= 2:
                        ask_sizes.append(float(a[1]))
                
                # Détecter si volumes similaires sur plusieurs niveaux consécutifs
                if len(bid_sizes) >= 5:
                    for i in range(len(bid_sizes) - 4):
                        window = bid_sizes[i:i+5]
                        if len(set([round(s, 2) for s in window])) <= 2:  # Max 2 valeurs différentes
                            iceberg_detected = True
                            break
                
                if not iceberg_detected and len(ask_sizes) >= 5:
                    for i in range(len(ask_sizes) - 4):
                        window = ask_sizes[i:i+5]
                        if len(set([round(s, 2) for s in window])) <= 2:
                            iceberg_detected = True
                            break
        except:
            pass
        
        return {
            'support_levels': [s['price'] for s in support_levels],
            'resistance_levels': [r['price'] for r in resistance_levels],
            'liquidity_zones': liquidity_zones,
            'order_book_imbalance': round(imbalance, 2),
            'wall_detected': closest_wall is not None,
            'wall_price': closest_wall['price'] if closest_wall else 0,
            'wall_side': wall_side,
            'wall_size': closest_wall['size'] if closest_wall else 0,
            'spread_percent': round(spread_percent, 4),
            'spread_abs': round(spread_abs, 2),
            'bid_ask_ratio': round(bid_ask_ratio, 2),
            'liquidity_depth': round(liquidity_depth, 2),
            'iceberg_detected': iceberg_detected,
            'best_bid': round(best_bid, 2),
            'best_ask': round(best_ask, 2)
        }
    
    def calculate_atr(self, candles: List[Dict], period: int = 14) -> float:
        """Calcule l'ATR (Average True Range) pour mesurer la volatilité"""
        if len(candles) < period + 1:
            return 0.0
        
        true_ranges = []
        for i in range(1, len(candles)):
            high = candles[i]['high']
            low = candles[i]['low']
            prev_close = candles[i-1]['close']
            
            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)
            
            true_range = max(tr1, tr2, tr3)
            true_ranges.append(true_range)
        
        if len(true_ranges) < period:
            return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0
        
        return sum(true_ranges[-period:]) / period
    
    def detect_volatility_regime(self, atr: float, price: float, candles: List[Dict]) -> Dict:
        """Détecte le régime de volatilité (faible, normale, élevée)"""
        if atr == 0 or price == 0:
            return {'regime': 'unknown', 'volatility_percent': 0, 'squeeze': False}
        
        atr_percent = (atr / price) * 100
        
        # Calculer le squeeze de Bollinger (BB width)
        if len(candles) >= 20:
            closes = [c['close'] for c in candles[-20:]]
            bb_range = max(closes) - min(closes)
            bb_width_percent = (bb_range / price) * 100
            
            # Squeeze : volatilité très faible (potentiel breakout)
            squeeze = bb_width_percent < atr_percent * 0.5
        else:
            squeeze = False
        
        # Classification
        if atr_percent < 0.3:
            regime = 'low'
        elif atr_percent < 0.8:
            regime = 'normal'
        else:
            regime = 'high'
        
        return {
            'regime': regime,
            'volatility_percent': round(atr_percent, 3),
            'squeeze': squeeze,
            'atr_value': round(atr, 2)
        }
    
    def identify_key_levels(self, candles: List[Dict], price: float) -> Dict:
        """
        Identifie les niveaux clés de support et résistance avec méthodes avancées
        Utilise: Swing Highs/Lows, Volume Profile, Zones de consolidation, Touches multiples
        """
        if len(candles) < 50:
            return {
                'supports': [],
                'resistances': [],
                'psychological_levels': [],
                'pivot_points': {},
                'consolidation_zones': []
            }
        
        # Calculer l'ATR pour la tolérance de clustering
        atr = self.calculate_atr(candles, 14)
        tolerance = max(atr * 0.5, price * 0.001)  # 0.5 ATR ou 0.1% du prix minimum
        
        # 1. DÉTECTION DES SWING HIGHS/LOWS (méthode professionnelle)
        # Swing High: High entouré de 3-5 bougies plus basses de chaque côté
        # Swing Low: Low entouré de 3-5 bougies plus hautes de chaque côté
        swing_period = 3  # Nombre de bougies de confirmation
        
        swing_highs = []  # [(price, index, strength)]
        swing_lows = []   # [(price, index, strength)]
        
        for i in range(swing_period, len(candles) - swing_period):
            high = candles[i]['high']
            low = candles[i]['low']
            
            # Vérifier si c'est un Swing High
            is_swing_high = True
            touches = 1  # Compter les touches du niveau
            
            # Vérifier les bougies précédentes
            for j in range(max(0, i - swing_period), i):
                if candles[j]['high'] >= high:
                    is_swing_high = False
                    break
                # Compter les touches proches (dans la tolérance)
                if abs(candles[j]['high'] - high) <= tolerance:
                    touches += 1
            
            # Vérifier les bougies suivantes
            if is_swing_high:
                for j in range(i + 1, min(len(candles), i + swing_period + 1)):
                    if candles[j]['high'] >= high:
                        is_swing_high = False
                        break
                    if abs(candles[j]['high'] - high) <= tolerance:
                        touches += 1
            
            if is_swing_high:
                # Calculer la force (basée sur les touches et le volume)
                volume_strength = candles[i].get('volume', 0) / max([c.get('volume', 1) for c in candles[max(0, i-10):i+10]], default=1)
                strength = min(touches * 0.3 + volume_strength * 0.7, 1.0)
                swing_highs.append((high, i, strength))
            
            # Vérifier si c'est un Swing Low
            is_swing_low = True
            touches = 1
            
            for j in range(max(0, i - swing_period), i):
                if candles[j]['low'] <= low:
                    is_swing_low = False
                    break
                if abs(candles[j]['low'] - low) <= tolerance:
                    touches += 1
            
            if is_swing_low:
                for j in range(i + 1, min(len(candles), i + swing_period + 1)):
                    if candles[j]['low'] <= low:
                        is_swing_low = False
                        break
                    if abs(candles[j]['low'] - low) <= tolerance:
                        touches += 1
            
            if is_swing_low:
                volume_strength = candles[i].get('volume', 0) / max([c.get('volume', 1) for c in candles[max(0, i-10):i+10]], default=1)
                strength = min(touches * 0.3 + volume_strength * 0.7, 1.0)
                swing_lows.append((low, i, strength))
        
        # 2. CLUSTERING DES NIVEAUX PROCHES (regrouper les niveaux similaires)
        def cluster_levels(levels_with_strength, tolerance):
            """Regroupe les niveaux proches et garde le plus fort"""
            if not levels_with_strength:
                return []
            
            # Trier par prix
            sorted_levels = sorted(levels_with_strength, key=lambda x: x[0])
            clusters = []
            current_cluster = [sorted_levels[0]]
            
            for level in sorted_levels[1:]:
                # Si le niveau est proche du cluster actuel
                if abs(level[0] - current_cluster[0][0]) <= tolerance:
                    current_cluster.append(level)
                else:
                    # Finaliser le cluster actuel (garder le plus fort)
                    best = max(current_cluster, key=lambda x: x[2])
                    clusters.append(best[0])
                    current_cluster = [level]
            
            # Ajouter le dernier cluster
            if current_cluster:
                best = max(current_cluster, key=lambda x: x[2])
                clusters.append(best[0])
            
            return clusters
        
        swing_highs_clustered = cluster_levels(swing_highs, tolerance)
        swing_lows_clustered = cluster_levels(swing_lows, tolerance)
        
        # 3. DÉTECTION DES ZONES DE CONSOLIDATION (price clustering)
        # Identifier les zones où le prix a passé beaucoup de temps
        price_clusters = {}
        recent_candles = candles[-100:]  # Analyser les 100 dernières bougies
        
        for candle in recent_candles:
            # Créer des buckets de prix
            high = candle['high']
            low = candle['low']
            close = candle['close']
            volume = candle.get('volume', 0)
            
            # Diviser en buckets selon l'ATR
            bucket_size = tolerance
            high_bucket = round(high / bucket_size) * bucket_size
            low_bucket = round(low / bucket_size) * bucket_size
            close_bucket = round(close / bucket_size) * bucket_size
            
            # Ajouter le volume à chaque bucket touché
            for bucket in [high_bucket, low_bucket, close_bucket]:
                price_clusters[bucket] = price_clusters.get(bucket, 0) + volume
        
        # Identifier les zones de forte consolidation (haut volume)
        if price_clusters:
            avg_volume = sum(price_clusters.values()) / len(price_clusters)
            consolidation_zones = []
            for cluster_price, cluster_volume in price_clusters.items():
                if cluster_volume > avg_volume * 1.5:  # 50% au-dessus de la moyenne
                    consolidation_zones.append({
                        'price': cluster_price,
                        'volume': cluster_volume,
                        'strength': min(cluster_volume / avg_volume, 3.0)  # Force max 3x
                    })
        
        # 4. VOLUME PROFILE pour identifier les zones de forte activité
        volume_profile = self.calculate_volume_profile(recent_candles)
        vah = volume_profile.get('vah', 0)
        val = volume_profile.get('val', 0)
        poc = volume_profile.get('poc', 0)
        
        # 5. MÉTHODE DES TOUCHES MULTIPLES
        # Identifier les niveaux qui ont été touchés plusieurs fois
        touch_levels = {}
        for candle in recent_candles:
            high = candle['high']
            low = candle['low']
            
            # Arrondir aux niveaux significatifs
            high_rounded = round(high / tolerance) * tolerance
            low_rounded = round(low / tolerance) * tolerance
            
            touch_levels[high_rounded] = touch_levels.get(high_rounded, 0) + 1
            touch_levels[low_rounded] = touch_levels.get(low_rounded, 0) + 1
        
        # Niveaux avec 3+ touches sont significatifs
        significant_touches = [price for price, touches in touch_levels.items() if touches >= 3]
        
        # 6. NIVEAUX PSYCHOLOGIQUES améliorés
        psychological_levels = []
        # Arrondir selon l'ordre de grandeur du prix
        if price >= 1000:
            round_base = 100  # Pour BTC, ETH
        elif price >= 100:
            round_base = 10
        elif price >= 10:
            round_base = 1
        else:
            round_base = 0.1
        
        price_rounded = round(price / round_base) * round_base
        for i in range(-3, 4):
            level = price_rounded + (i * round_base)
            if level > 0 and abs(level - price) <= price * 0.1:  # Dans 10% du prix
                psychological_levels.append(level)
        
        # 7. PIVOT POINTS améliorés (Fibonacci + Camarilla)
        last_candle = candles[-1]
        high = last_candle['high']
        low = last_candle['low']
        close = last_candle['close']
        
        # Pivot classique
        pivot = (high + low + close) / 3
        range_val = high - low
        
        # Pivot Points classiques
        r1_classic = 2 * pivot - low
        s1_classic = 2 * pivot - high
        r2_classic = pivot + range_val
        s2_classic = pivot - range_val
        r3_classic = high + 2 * (pivot - low)
        s3_classic = low - 2 * (high - pivot)
        
        # Pivot Points Fibonacci
        r1_fib = pivot + 0.382 * range_val
        r2_fib = pivot + 0.618 * range_val
        r3_fib = pivot + 1.000 * range_val
        s1_fib = pivot - 0.382 * range_val
        s2_fib = pivot - 0.618 * range_val
        s3_fib = pivot - 1.000 * range_val
        
        # Pivot Points Camarilla
        r1_cam = close + range_val * 1.1 / 12
        r2_cam = close + range_val * 1.1 / 6
        r3_cam = close + range_val * 1.1 / 4
        r4_cam = close + range_val * 1.1 / 2
        s1_cam = close - range_val * 1.1 / 12
        s2_cam = close - range_val * 1.1 / 6
        s3_cam = close - range_val * 1.1 / 4
        s4_cam = close - range_val * 1.1 / 2
        
        # 8. COMBINER TOUS LES NIVEAUX ET FILTRER
        
        # Supports: Swing lows + VAL + POC + Touches significatives sous le prix
        all_supports = []
        
        # Swing lows sous le prix actuel
        for swing_low in swing_lows_clustered:
            if swing_low < price and swing_low > price * 0.9:  # Dans 10% sous le prix
                all_supports.append(swing_low)
        
        # Volume Profile
        if val > 0 and val < price:
            all_supports.append(val)
        if poc > 0 and poc < price:
            all_supports.append(poc)
        
        # Touches significatives sous le prix
        for touch in significant_touches:
            if touch < price and touch > price * 0.9:
                all_supports.append(touch)
        
        # Pivot Points supports
        for s in [s1_classic, s2_classic, s1_fib, s2_fib, s1_cam, s2_cam]:
            if s < price and s > 0:
                all_supports.append(s)
        
        # Résistances: Swing highs + VAH + POC + Touches significatives au-dessus du prix
        all_resistances = []
        
        # Swing highs au-dessus du prix actuel
        for swing_high in swing_highs_clustered:
            if swing_high > price and swing_high < price * 1.1:  # Dans 10% au-dessus du prix
                all_resistances.append(swing_high)
        
        # Volume Profile
        if vah > 0 and vah > price:
            all_resistances.append(vah)
        if poc > 0 and poc > price:
            all_resistances.append(poc)
        
        # Touches significatives au-dessus du prix
        for touch in significant_touches:
            if touch > price and touch < price * 1.1:
                all_resistances.append(touch)
        
        # Pivot Points résistances
        for r in [r1_classic, r2_classic, r1_fib, r2_fib, r1_cam, r2_cam]:
            if r > price and r > 0:
                all_resistances.append(r)
        
        # Clustering final et tri par proximité au prix
        def final_cluster_and_sort(levels, current_price, tolerance):
            """Clustering final et tri par distance au prix"""
            if not levels:
                return []
            
            # Clustering
            sorted_levels = sorted(levels)
            clustered = []
            current = sorted_levels[0]
            
            for level in sorted_levels[1:]:
                if abs(level - current) <= tolerance:
                    # Moyenne pondérée
                    current = (current + level) / 2
                else:
                    clustered.append(current)
                    current = level
            clustered.append(current)
            
            # Trier par distance au prix (les plus proches en premier)
            clustered.sort(key=lambda x: abs(x - current_price))
            
            return clustered[:5]  # Top 5
        
        final_supports = final_cluster_and_sort(all_supports, price, tolerance)
        final_resistances = final_cluster_and_sort(all_resistances, price, tolerance)
        
        return {
            'supports': [round(s, 2) for s in final_supports],
            'resistances': [round(r, 2) for r in final_resistances],
            'psychological_levels': [round(p, 2) for p in psychological_levels[:3]],
            'pivot_points': {
                'pivot': round(pivot, 2),
                'classic': {
                    'r1': round(r1_classic, 2),
                    'r2': round(r2_classic, 2),
                    'r3': round(r3_classic, 2),
                    's1': round(s1_classic, 2),
                    's2': round(s2_classic, 2),
                    's3': round(s3_classic, 2)
                },
                'fibonacci': {
                    'r1': round(r1_fib, 2),
                    'r2': round(r2_fib, 2),
                    'r3': round(r3_fib, 2),
                    's1': round(s1_fib, 2),
                    's2': round(s2_fib, 2),
                    's3': round(s3_fib, 2)
                },
                'camarilla': {
                    'r1': round(r1_cam, 2),
                    'r2': round(r2_cam, 2),
                    'r3': round(r3_cam, 2),
                    'r4': round(r4_cam, 2),
                    's1': round(s1_cam, 2),
                    's2': round(s2_cam, 2),
                    's3': round(s3_cam, 2),
                    's4': round(s4_cam, 2)
                }
            },
            'consolidation_zones': [{'price': round(z['price'], 2), 'strength': round(z['strength'], 2)} for z in consolidation_zones[:5]] if 'consolidation_zones' in locals() else [],
            'volume_profile_levels': {
                'poc': round(poc, 2),
                'vah': round(vah, 2),
                'val': round(val, 2)
            },
            'swing_highs_count': len(swing_highs),
            'swing_lows_count': len(swing_lows),
            'tolerance_used': round(tolerance, 2)
        }
    
    def detect_candlestick_patterns(self, candles: List[Dict]) -> List[Dict]:
        """Détecte les patterns de chandeliers japonais"""
        if len(candles) < 3:
            return []
        
        patterns = []
        recent = candles[-3:]
        
        # Doji (indécision)
        c = recent[-1]
        body = abs(c['close'] - c['open'])
        total_range = c['high'] - c['low']
        if total_range > 0 and body / total_range < 0.1:
            patterns.append({
                'pattern': 'Doji',
                'signal': 'NEUTRAL',
                'strength': 'medium',
                'description': 'Indécision du marché'
            })
        
        # Hammer / Hanging Man
        if len(recent) >= 1:
            c = recent[-1]
            body = abs(c['close'] - c['open'])
            lower_shadow = min(c['open'], c['close']) - c['low']
            upper_shadow = c['high'] - max(c['open'], c['close'])
            
            if lower_shadow > body * 2 and upper_shadow < body * 0.5:
                if c['close'] > c['open']:
                    patterns.append({
                        'pattern': 'Hammer',
                        'signal': 'BUY',
                        'strength': 'strong',
                        'description': 'Signal haussier de rebond'
                    })
                else:
                    patterns.append({
                        'pattern': 'Hanging Man',
                        'signal': 'SELL',
                        'strength': 'medium',
                        'description': 'Signal baissier potentiel'
                    })
        
        # Engulfing
        if len(recent) >= 2:
            prev = recent[-2]
            curr = recent[-1]
            
            prev_body = abs(prev['close'] - prev['open'])
            curr_body = abs(curr['close'] - curr['open'])
            
            # Bullish Engulfing
            if prev['close'] < prev['open'] and curr['close'] > curr['open']:
                if curr['open'] < prev['close'] and curr['close'] > prev['open']:
                    if curr_body > prev_body * 1.1:
                        patterns.append({
                            'pattern': 'Bullish Engulfing',
                            'signal': 'BUY',
                            'strength': 'strong',
                            'description': 'Reversement haussier'
                        })
            
            # Bearish Engulfing
            if prev['close'] > prev['open'] and curr['close'] < curr['open']:
                if curr['open'] > prev['close'] and curr['close'] < prev['open']:
                    if curr_body > prev_body * 1.1:
                        patterns.append({
                            'pattern': 'Bearish Engulfing',
                            'signal': 'SELL',
                            'strength': 'strong',
                            'description': 'Reversement baissier'
                        })
        
        return patterns
    
    def detect_divergence(self, prices: List[float], rsi_values: List[float]) -> Optional[Dict]:
        """Détecte les divergences entre le prix et le RSI"""
        if len(prices) < 10 or len(rsi_values) < 10:
            return None
        
        # Comparer les 5 dernières périodes avec les 5 précédentes
        recent_prices = prices[-5:]
        recent_rsi = rsi_values[-5:]
        prev_prices = prices[-10:-5]
        prev_rsi = rsi_values[-10:-5]
        
        price_trend = recent_prices[-1] > recent_prices[0]
        rsi_trend = recent_rsi[-1] > recent_rsi[0]
        
        # Divergence haussière : prix baisse mais RSI monte
        if not price_trend and rsi_trend:
            if min(recent_prices) < min(prev_prices) and min(recent_rsi) > min(prev_rsi):
                return {
                    'type': 'bullish',
                    'signal': 'BUY',
                    'strength': 'strong',
                    'description': 'Divergence haussière : prix baisse mais momentum augmente'
                }
        
        # Divergence baissière : prix monte mais RSI baisse
        if price_trend and not rsi_trend:
            if max(recent_prices) > max(prev_prices) and max(recent_rsi) < max(prev_rsi):
                return {
                    'type': 'bearish',
                    'signal': 'SELL',
                    'strength': 'strong',
                    'description': 'Divergence baissière : prix monte mais momentum diminue'
                }
        
        return None
    
    def calculate_momentum(self, prices: List[float], period: int = 10) -> Dict:
        """Calcule le momentum et la vitesse du mouvement"""
        if len(prices) < period:
            return {'momentum': 0, 'velocity': 0, 'acceleration': 0}
        
        # Momentum : changement de prix sur la période
        momentum = prices[-1] - prices[-period]
        momentum_percent = (momentum / prices[-period]) * 100 if prices[-period] > 0 else 0
        
        # Velocity : taux de changement
        if period >= 2:
            velocity = (prices[-1] - prices[-2]) / prices[-2] * 100 if prices[-2] > 0 else 0
        else:
            velocity = 0
        
        # Acceleration : changement de velocity
        if period >= 3:
            prev_velocity = (prices[-2] - prices[-3]) / prices[-3] * 100 if prices[-3] > 0 else 0
            acceleration = velocity - prev_velocity
        else:
            acceleration = 0
        
        return {
            'momentum': round(momentum, 2),
            'momentum_percent': round(momentum_percent, 3),
            'velocity': round(velocity, 3),
            'acceleration': round(acceleration, 3)
        }
    
    def calculate_stochastic(self, candles: List[Dict], period: int = 14) -> Dict[str, float]:
        """Calcule le Stochastic Oscillator (signaux rapides)"""
        if len(candles) < period:
            return {'k': 50, 'd': 50}
        
        recent = candles[-period:]
        low = min(c['low'] for c in recent)
        high = max(c['high'] for c in recent)
        close = recent[-1]['close']
        
        if high == low:
            k = 50
        else:
            k = ((close - low) / (high - low)) * 100
        
        # %D = moyenne mobile de %K sur 3 périodes
        if len(candles) >= period + 2:
            k_values = []
            for i in range(period, len(candles)):
                sub_candles = candles[i-period:i+1]
                sub_low = min(c['low'] for c in sub_candles)
                sub_high = max(c['high'] for c in sub_candles)
                sub_close = sub_candles[-1]['close']
                if sub_high == sub_low:
                    k_val = 50
                else:
                    k_val = ((sub_close - sub_low) / (sub_high - sub_low)) * 100
                k_values.append(k_val)
            d = sum(k_values[-3:]) / min(3, len(k_values))
        else:
            d = k
        
        return {'k': round(k, 2), 'd': round(d, 2)}
    
    def calculate_williams_r(self, candles: List[Dict], period: int = 14) -> float:
        """Calcule le Williams %R (signaux rapides)"""
        if len(candles) < period:
            return -50.0
        
        recent = candles[-period:]
        high = max(c['high'] for c in recent)
        low = min(c['low'] for c in recent)
        close = recent[-1]['close']
        
        if high == low:
            return -50.0
        
        wr = ((high - close) / (high - low)) * -100
        return round(wr, 2)
    
    def calculate_cci(self, candles: List[Dict], period: int = 20) -> float:
        """Calcule le Commodity Channel Index (CCI)"""
        if len(candles) < period:
            return 0.0
        
        recent = candles[-period:]
        typical_prices = [(c['high'] + c['low'] + c['close']) / 3 for c in recent]
        sma = sum(typical_prices) / period
        mean_deviation = sum(abs(tp - sma) for tp in typical_prices) / period
        
        if mean_deviation == 0:
            return 0.0
        
        cci = (typical_prices[-1] - sma) / (0.015 * mean_deviation)
        return round(cci, 2)
    
    def calculate_vwap(self, candles: List[Dict], period: int = None) -> float:
        """
        Calcule le VWAP (Volume Weighted Average Price) intraday
        Pour scalping: VWAP sur les dernières N bougies
        """
        if not candles:
            return 0.0
        
        # Utiliser toutes les bougies de la journée ou période spécifiée
        if period is None:
            # Par défaut: toutes les bougies disponibles (intraday)
            period = len(candles)
        
        recent = candles[-period:] if len(candles) > period else candles
        
        total_volume_price = sum(c['close'] * c.get('volume', 0) for c in recent)
        total_volume = sum(c.get('volume', 0) for c in recent)
        
        if total_volume == 0:
            return candles[-1]['close'] if candles else 0.0
        
        vwap = total_volume_price / total_volume
        return round(vwap, 2)
    
    def calculate_order_flow_delta(self, trades: List[Dict] = None) -> Dict:
        """
        Calcule l'Order Flow Delta (buy volume - sell volume)
        Pour scalping: analyse des trades récents
        """
        if not trades or len(trades) < 10:
            return {
                'delta': 0,
                'buy_volume': 0,
                'sell_volume': 0,
                'delta_percent': 0
            }
        
        buy_volume = 0
        sell_volume = 0
        
        for trade in trades[-50:]:  # 50 derniers trades
            # Déterminer si c'est un buy ou sell (aggressor)
            # Format attendu: {'side': 'buy'/'sell', 'size': float, 'price': float}
            side = trade.get('side', '').lower()
            size = float(trade.get('size', trade.get('sz', 0)))
            
            if side in ['buy', 'b']:
                buy_volume += size
            elif side in ['sell', 's']:
                sell_volume += size
        
        delta = buy_volume - sell_volume
        total_volume = buy_volume + sell_volume
        delta_percent = (delta / total_volume * 100) if total_volume > 0 else 0
        
        return {
            'delta': round(delta, 2),
            'buy_volume': round(buy_volume, 2),
            'sell_volume': round(sell_volume, 2),
            'delta_percent': round(delta_percent, 2)
        }
    
    def calculate_cumulative_delta(self, trades: List[Dict] = None) -> Dict:
        """
        Calcule le Cumulative Delta (somme cumulative des deltas)
        Indicateur de momentum pour scalping
        """
        if not trades or len(trades) < 10:
            return {
                'cumulative_delta': 0,
                'delta_trend': 'neutral'
            }
        
        cumulative = 0
        deltas = []
        
        for trade in trades[-100:]:  # 100 derniers trades
            side = trade.get('side', '').lower()
            size = float(trade.get('size', trade.get('sz', 0)))
            
            if side in ['buy', 'b']:
                cumulative += size
            elif side in ['sell', 's']:
                cumulative -= size
            
            deltas.append(cumulative)
        
        # Déterminer la tendance
        if len(deltas) >= 2:
            trend = 'bullish' if deltas[-1] > deltas[-10] else 'bearish' if deltas[-1] < deltas[-10] else 'neutral'
        else:
            trend = 'neutral'
        
        return {
            'cumulative_delta': round(cumulative, 2),
            'delta_trend': trend,
            'delta_values': deltas[-20:]  # 20 dernières valeurs
        }
    
    def detect_price_action_signals(self, candles: List[Dict], price: float) -> List[Dict]:
        """Détecte les signaux basés sur l'action du prix (très rapide)"""
        if len(candles) < 5:
            return []
        
        signals = []
        recent = candles[-5:]
        
        # Breakout detection
        if len(recent) >= 3:
            # Breakout haussier : prix casse au-dessus des 3 dernières bougies
            if price > max(c['high'] for c in recent[-3:]):
                signals.append({
                    'type': 'breakout',
                    'signal': 'BUY',
                    'strength': 'strong',
                    'description': 'Breakout haussier - prix casse la résistance'
                })
            
            # Breakout baissier : prix casse en-dessous des 3 dernières bougies
            if price < min(c['low'] for c in recent[-3:]):
                signals.append({
                    'type': 'breakout',
                    'signal': 'SELL',
                    'strength': 'strong',
                    'description': 'Breakout baissier - prix casse le support'
                })
        
        # Reversal detection (changement de direction)
        if len(recent) >= 3:
            closes = [c['close'] for c in recent]
            # Reversement haussier : 2 baisses puis 1 hausse
            if closes[-3] > closes[-2] and closes[-2] > closes[-1] and recent[-1]['close'] > recent[-1]['open']:
                signals.append({
                    'type': 'reversal',
                    'signal': 'BUY',
                    'strength': 'medium',
                    'description': 'Reversement haussier détecté'
                })
            
            # Reversement baissier : 2 hausses puis 1 baisse
            if closes[-3] < closes[-2] and closes[-2] < closes[-1] and recent[-1]['close'] < recent[-1]['open']:
                signals.append({
                    'type': 'reversal',
                    'signal': 'SELL',
                    'strength': 'medium',
                    'description': 'Reversement baissier détecté'
                })
        
        return signals
    
    def calculate_sl_tp(
        self,
        signal: str,
        price: float,
        bollinger: Dict[str, float] = None,
        volume_profile: Dict[str, float] = None,
        ema20: float = None,
        ema50: float = None,
        rsi: float = None,
        atr: float = None,
        fees: Dict[str, float] = None
    ) -> Dict[str, float]:
        """
        Calcule les niveaux de Stop Loss et Take Profit pour SCALPING AGRESSIF
        SL: 0.3% à 0.8% | TP: 1.0%, 1.8%, 2.5% (multi-niveaux)
        """
        if signal == "NEUTRE":
            return {
                'stop_loss': 0,
                'take_profit': 0,
                'take_profit_1': 0,
                'take_profit_2': 0,
                'take_profit_3': 0,
                'stop_loss_percent': 0,
                'take_profit_percent': 0,
                'risk_reward': 0,
                'fees': fees or {}
            }
        
        # Frais par défaut si non fournis
        if fees is None:
            try:
                import config
                api_config = config.HYPERLIQUID_API
                fees = self.get_hyperliquid_fees(
                    volume_14d=api_config.get('volume_14d', api_config.get('volume_30d', 0)),
                    use_referral=api_config.get('use_referral', False),
                    staking_tier=api_config.get('staking_tier', None)
                )
            except:
                fees = self.get_hyperliquid_fees()
        
        # Configuration scalping depuis config.py
        try:
            import config
            max_sl_percent = getattr(config, 'MAX_STOP_LOSS_PERCENT', 0.8)
            min_sl_percent = getattr(config, 'MIN_STOP_LOSS_PERCENT', 0.3)
            tp1_percent = getattr(config, 'TP1_PERCENT', 1.0)
            tp2_percent = getattr(config, 'TP2_PERCENT', 1.8)
            tp3_percent = getattr(config, 'TP3_PERCENT', 2.5)
        except:
            max_sl_percent = 0.8
            min_sl_percent = 0.3
            tp1_percent = 1.0
            tp2_percent = 1.8
            tp3_percent = 2.5
        
        # Utiliser ATR si disponible, sinon estimation
        if atr and atr > 0:
            # SL basé sur ATR: 0.5x à 1.5x ATR
            atr_sl_percent = (atr / price) * 100
            sl_percent = max(min_sl_percent, min(max_sl_percent, atr_sl_percent * 0.8))
        else:
            # SL par défaut: moyenne entre min et max
            sl_percent = (min_sl_percent + max_sl_percent) / 2
        
        # Calcul basé sur les Bollinger Bands et Volume Profile (si disponibles)
        if bollinger and volume_profile:
            bb_range = bollinger['upper'] - bollinger['lower']
            atr_estimate = bb_range / 4
        
        # Ajouter les frais dans le calcul (frais taker pour entrée et sortie)
        # Utiliser les frais effectifs avec réductions appliquées
        taker_fee_effective = fees.get('effective_taker_percent', fees.get('taker_percent', 0.035))
        total_fees_percent = (taker_fee_effective / 100) * 2  # Entrée + sortie (en décimal)
        
        # SCALPING: Calculs simplifiés avec pourcentages fixes
        if signal == "ACHAT":
            # Stop Loss: prix - SL%
            stop_loss = price * (1 - sl_percent / 100)
            
            # Take Profit multi-niveaux
            take_profit_1 = price * (1 + tp1_percent / 100)
            take_profit_2 = price * (1 + tp2_percent / 100)
            take_profit_3 = price * (1 + tp3_percent / 100)
            take_profit = take_profit_3  # Principal = TP3
            
        else:  # VENTE
            # Stop Loss: prix + SL%
            stop_loss = price * (1 + sl_percent / 100)
            
            # Take Profit multi-niveaux
            take_profit_1 = price * (1 - tp1_percent / 100)
            take_profit_2 = price * (1 - tp2_percent / 100)
            take_profit_3 = price * (1 - tp3_percent / 100)
            take_profit = take_profit_3  # Principal = TP3
        
        # Calculs des pourcentages
        if signal == "ACHAT":
            sl_percent_calc = ((price - stop_loss) / price) * 100
            tp_percent_calc = ((take_profit - price) / price) * 100
        else:
            sl_percent_calc = ((stop_loss - price) / price) * 100
            tp_percent_calc = ((price - take_profit) / price) * 100
        
        # Risk/Reward Ratio (net après frais)
        risk_reward = tp_percent_calc / sl_percent_calc if sl_percent_calc > 0 else 0
        
        # Calcul du gain/perte net après frais
        if signal == "ACHAT":
            net_gain_percent = tp_percent_calc - total_fees_percent * 100
            net_loss_percent = sl_percent_calc + total_fees_percent * 100
        else:
            net_gain_percent = tp_percent_calc - total_fees_percent * 100
            net_loss_percent = sl_percent_calc + total_fees_percent * 100
        
        return {
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(take_profit, 2),
            'take_profit_1': round(take_profit_1, 2),
            'take_profit_2': round(take_profit_2, 2),
            'take_profit_3': round(take_profit_3, 2),
            'stop_loss_percent': round(sl_percent_calc, 2),
            'take_profit_percent': round(tp_percent_calc, 2),
            'risk_reward': round(risk_reward, 2),
            'fees': fees,
            'total_fees_percent': round(total_fees_percent * 100, 3),
            'net_gain_percent': round(net_gain_percent, 2),
            'net_loss_percent': round(net_loss_percent, 2),
            'break_even': round(price * (1 + total_fees_percent) if signal == "ACHAT" else price * (1 - total_fees_percent), 2)
        }
    
    def validate_signal_context(self, signal_type: str, rsi: float, ema20: float, ema50: float, 
                                price: float, macd: Dict, stochastic: Dict, williams_r: float, 
                                volume_ratio: float) -> Tuple[bool, Dict, str]:
        """
        Validation croisée pour éviter faux signaux
        """
        if signal_type == 'ACHAT' or signal_type == 'BUY':
            # TOUS ces critères doivent être vrais pour un BUY valide
            checks = {
                'rsi_ok': rsi < 55,  # Pas suracheté
                'trend_ok': price > ema50 or (ema20 > ema50),  # Trend haussier
                'macd_ok': macd.get('histogram', 0) > -0.5,  # Pas trop baissier
                'stochastic_ok': stochastic.get('%K', 50) < 75 if isinstance(stochastic, dict) else True,
                'williams_ok': williams_r > -30,  # Pas suracheté
                'volume_ok': volume_ratio >= 2.0
            }
        else:  # VENTE / SELL
            checks = {
                'rsi_ok': rsi > 45,
                'trend_ok': price < ema50 or (ema20 < ema50),
                'macd_ok': macd.get('histogram', 0) < 0.5,
                'stochastic_ok': stochastic.get('%K', 50) > 25 if isinstance(stochastic, dict) else True,
                'williams_ok': williams_r < -70,
                'volume_ok': volume_ratio >= 2.0
            }
        
        passed = sum(checks.values())
        total = len(checks)
        
        # Au moins 5/6 critères doivent passer
        return passed >= 5, checks, f"{passed}/{total}"
    
    def should_enter_trade(self, analysis: Dict) -> Tuple[bool, str]:
        """
        Filtres en 2 étapes : basique + validation contexte
        """
        try:
            import config
        except:
            return False, "Config non disponible"
        
        signal_quality = self._calculate_signal_quality(analysis)
        current_price = analysis.get('current_price', 0)
        candles = analysis.get('candles', [])
        atr = analysis.get('indicators', {}).get('atr', 0)
        spread = analysis.get('spread', 0.1)
        
        # Calculer volume ratio
        volume_ratio = 0
        if len(candles) >= 20:
            recent_volume = sum(c.get('volume', 0) for c in candles[-5:])
            avg_volume = sum(c.get('volume', 0) for c in candles[-20:]) / 20
            if avg_volume > 0:
                volume_ratio = recent_volume / (avg_volume * 5)
        
        # ATR percent
        atr_percent = (atr / current_price) if current_price > 0 and atr > 0 else 0
        
        # Signal type
        signal = analysis.get('signal', 'NEUTRE')
        signal_type = 'ACHAT' if signal == 'ACHAT' else 'VENTE'
        
        # Étape 1 : Filtres basiques
        basic_checks = {
            'quality': signal_quality >= getattr(config, 'SIGNAL_QUALITY_THRESHOLD', 82),
            'volume': volume_ratio >= getattr(config, 'MIN_VOLUME_MULTIPLIER', 2.5) if len(candles) >= 20 else False,
            'spread': spread <= getattr(config, 'MAX_SPREAD_PERCENT', 0.03),
            'atr_range': 0.005 <= atr_percent <= 0.012 if atr_percent > 0 else False,
            'no_position': True,
            'capital_ok': True
        }
        
        # Vérifier position manager
        try:
            if hasattr(self, 'position_manager') and self.position_manager:
                can_open, reason = self.position_manager.can_open_position(self.coin, 10000)
                basic_checks['no_position'] = can_open
                basic_checks['capital_ok'] = can_open
        except:
            pass
        
        if not all(basic_checks.values()):
            failed = [k for k, v in basic_checks.items() if not v]
            return False, f"Filtres basiques échoués: {', '.join(failed)}"
        
        # Étape 2 : Validation contexte
        indicators = analysis.get('indicators', {})
        rsi = indicators.get('rsi', 50)
        macd = indicators.get('macd', {'histogram': 0})
        ema20 = indicators.get('ema20', 0)
        ema50 = indicators.get('ema50', 0)
        stochastic = indicators.get('stochastic', {})
        williams_r = indicators.get('williams_r', -50)
        
        context_valid, context_checks, context_score = self.validate_signal_context(
            signal_type, rsi, ema20, ema50, current_price, macd, 
            stochastic, williams_r, volume_ratio
        )
        
        if not context_valid:
            return False, f"Validation contexte échouée: {context_score} - {context_checks}"
        
        return True, "OK"
    
    def _calculate_signal_quality(self, analysis: Dict) -> float:
        """
        Calcule le score de qualité du signal (0-100) avec confluence renforcée
        """
        signal_details = analysis.get('signal_details', {})
        buy_signals = signal_details.get('buy_signals', 0)
        sell_signals = signal_details.get('sell_signals', 0)
        
        indicators = analysis.get('indicators', {})
        rsi = indicators.get('rsi', 50)
        macd = indicators.get('macd', {'histogram': 0})
        ema20 = indicators.get('ema20', 0)
        ema50 = indicators.get('ema50', 0)
        current_price = analysis.get('current_price', 0)
        
        # Volume ratio
        candles = analysis.get('candles', [])
        volume_ratio = 0
        if len(candles) >= 20:
            recent_volume = sum(c.get('volume', 0) for c in candles[-5:])
            avg_volume = sum(c.get('volume', 0) for c in candles[-20:]) / 20
            if avg_volume > 0:
                volume_ratio = recent_volume / (avg_volume * 5)
        
        # Spread
        spread = analysis.get('spread', 0.1)
        spread_percent = spread
        
        # ATR percent
        atr = indicators.get('atr', 0)
        atr_percent = (atr / current_price) if current_price > 0 and atr > 0 else 0
        
        # Order book imbalance
        order_book = analysis.get('advanced_analysis', {}).get('order_book', {})
        order_book_imbalance = order_book.get('order_book_imbalance', 0)
        
        # Key levels
        key_levels = analysis.get('advanced_analysis', {}).get('key_levels', {})
        
        return self.calculate_signal_quality_detailed(
            buy_signals, sell_signals, rsi, macd, ema20, ema50, current_price,
            volume_ratio, spread_percent, atr_percent, order_book_imbalance, key_levels
        )
    
    def calculate_signal_quality_detailed(self, buy_signals, sell_signals, rsi, macd, ema20, ema50,
                                          price, volume_ratio, spread_percent, atr_percent,
                                          order_book_imbalance, key_levels):
        """
        Score 0-100 basé sur confluence + contexte de marché
        """
        score = 0
        max_score = 100
        
        # 1. CONFLUENCE D'INDICATEURS (40 points)
        signal_diff = abs(buy_signals - sell_signals)
        if signal_diff >= 5:
            score += 20
        elif signal_diff >= 4:
            score += 15
        elif signal_diff >= 3:
            score += 10
        elif signal_diff >= 2:
            score += 5
        
        # Trend alignment (EMA + MACD)
        if buy_signals > sell_signals:
            if price > ema20 > ema50 and macd.get('histogram', 0) > 0:
                score += 20  # Trend confirmé
            elif price > ema20:
                score += 10
        else:
            if price < ema20 < ema50 and macd.get('histogram', 0) < 0:
                score += 20
            elif price < ema20:
                score += 10
        
        # 2. VOLUME (15 points)
        if volume_ratio >= 3.0:
            score += 15
        elif volume_ratio >= 2.5:
            score += 10
        elif volume_ratio >= 2.0:
            score += 5
        
        # 3. SPREAD (10 points)
        if spread_percent <= 0.02:
            score += 10
        elif spread_percent <= 0.03:
            score += 5
        
        # 4. VOLATILITÉ (10 points)
        if 0.005 <= atr_percent <= 0.01:  # Sweet spot
            score += 10
        elif 0.004 <= atr_percent <= 0.012:
            score += 5
        
        # 5. ORDER BOOK (10 points)
        if abs(order_book_imbalance) >= 20:
            if (order_book_imbalance > 0 and buy_signals > sell_signals) or \
               (order_book_imbalance < 0 and sell_signals > buy_signals):
                score += 10
        elif abs(order_book_imbalance) >= 15:
            score += 5
        
        # 6. PROXIMITÉ SUPPORT/RÉSISTANCE (15 points)
        supports = key_levels.get('supports', [])
        resistances = key_levels.get('resistances', [])
        
        # Long près support
        if buy_signals > sell_signals and supports:
            for support in supports[:2]:
                if support > 0:
                    distance = abs(price - support) / price
                    if distance <= 0.003:  # 0.3%
                        score += 15
                        break
                    elif distance <= 0.005:
                        score += 10
                        break
        
        # Short près résistance
        if sell_signals > buy_signals and resistances:
            for resistance in resistances[:2]:
                if resistance > 0:
                    distance = abs(price - resistance) / price
                    if distance <= 0.003:
                        score += 15
                        break
                    elif distance <= 0.005:
                        score += 10
                        break
        
        return min(score, max_score)
    
    def generate_trading_signal(
        self,
        rsi: float,
        macd: Dict[str, float],
        ema20: float,
        ema50: float,
        price: float,
        bollinger: Dict[str, float],
        order_flow: float
    ) -> Tuple[str, Dict]:
        """Génère un signal de trading basé sur tous les indicateurs"""
        buy_signals = 0
        sell_signals = 0
        reasons = []
        
        # RSI
        if rsi < 30:
            buy_signals += 2
            reasons.append("RSI < 30 (survendu)")
        elif rsi < 40:
            buy_signals += 1
            reasons.append("RSI < 40 (légèrement survendu)")
        elif rsi > 70:
            sell_signals += 2
            reasons.append("RSI > 70 (suracheté)")
        elif rsi > 60:
            sell_signals += 1
            reasons.append("RSI > 60 (légèrement suracheté)")
        
        # MACD
        if macd['histogram'] > 0 and macd['value'] > macd['signal']:
            buy_signals += 1
            reasons.append("MACD haussier (histogramme positif)")
        elif macd['histogram'] < 0 and macd['value'] < macd['signal']:
            sell_signals += 1
            reasons.append("MACD baissier (histogramme négatif)")
        
        # EMA Crossover
        if ema20 > ema50:
            buy_signals += 1
            reasons.append("EMA 20 > EMA 50 (Golden Cross)")
        elif ema20 < ema50:
            sell_signals += 1
            reasons.append("EMA 20 < EMA 50 (Death Cross)")
        
        # Prix vs EMA
        if price > ema20 and price > ema50:
            buy_signals += 1
            reasons.append("Prix au-dessus des EMA 20 et 50")
        elif price < ema20 and price < ema50:
            sell_signals += 1
            reasons.append("Prix en-dessous des EMA 20 et 50")
        
        # Bollinger Bands
        if price < bollinger['lower']:
            buy_signals += 1
            reasons.append("Prix en-dessous de la bande inférieure BB (rebond possible)")
        elif price > bollinger['upper']:
            sell_signals += 1
            reasons.append("Prix au-dessus de la bande supérieure BB (retournement possible)")
        
        # Order Flow
        if order_flow > 10:
            buy_signals += 1
            reasons.append(f"Order flow positif ({order_flow:.1f}%) - pression d'achat")
        elif order_flow < -10:
            sell_signals += 1
            reasons.append(f"Order flow négatif ({order_flow:.1f}%) - pression de vente")
        
        # Détermination du signal final
        if buy_signals > sell_signals + 1:
            signal = "ACHAT"
            strength = min(buy_signals, 5) / 5.0
        elif sell_signals > buy_signals + 1:
            signal = "VENTE"
            strength = min(sell_signals, 5) / 5.0
        else:
            signal = "NEUTRE"
            strength = 0.5
        
        return signal, {
            'strength': strength,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'reasons': reasons
        }
    
    def analyze(self) -> Dict:
        """Effectue une analyse complète et génère un signal avec toutes les fonctionnalités avancées"""
        if len(self.candles) < 50:
            return {
                'error': 'Pas assez de données historiques',
                'candles_count': len(self.candles)
            }
        
        closes = [c['close'] for c in self.candles]
        
        # Calcul des indicateurs de base
        rsi = self.calculate_rsi(closes, 14)
        macd = self.calculate_macd(closes)
        ema20 = self.calculate_ema(closes, 20)
        ema50 = self.calculate_ema(closes, 50)
        bollinger = self.calculate_bollinger_bands(closes, 20, 2)
        volume_profile = self.calculate_volume_profile(self.candles)
        
        # NOUVELLES FONCTIONNALITÉS AVANCÉES
        
        # 1. Récupérer le carnet d'ordres si vide
        if not self.order_book.get('bids') or not self.order_book.get('asks'):
            self.fetch_order_book()
        
        # 2. Analyse approfondie du carnet d'ordres
        order_book_analysis = {}
        if self.order_book.get('bids') and self.order_book.get('asks') and len(self.order_book['bids']) > 0 and len(self.order_book['asks']) > 0:
            order_book_analysis = self.analyze_order_book_depth(
                self.order_book['bids'],
                self.order_book['asks'],
                self.current_price
            )
        else:
            # Si toujours vide, retourner une structure vide mais valide
            order_book_analysis = {
                'support_levels': [],
                'resistance_levels': [],
                'liquidity_zones': [],
                'order_book_imbalance': 0,
                'wall_detected': False,
                'wall_price': 0,
                'wall_side': None,
                'wall_size': 0,
                'error': 'Order book non disponible'
            }
        
        # 2. Volatilité et ATR
        atr = self.calculate_atr(self.candles, 14)
        volatility_regime = self.detect_volatility_regime(atr, self.current_price, self.candles)
        
        # 3. Identification des niveaux clés
        key_levels = self.identify_key_levels(self.candles, self.current_price)
        
        # 4. Détection de patterns de chandeliers
        candlestick_patterns = self.detect_candlestick_patterns(self.candles)
        
        # 5. Détection de divergences
        # Calculer RSI historique pour la divergence
        rsi_history = []
        for i in range(14, len(closes)):
            rsi_val = self.calculate_rsi(closes[:i+1], 14)
            rsi_history.append(rsi_val)
        
        divergence = None
        if len(rsi_history) >= 10:
            divergence = self.detect_divergence(closes[-len(rsi_history):], rsi_history)
        
        # 6. Momentum et micro-structure
        momentum = self.calculate_momentum(closes, 10)
        
        # 7. NOUVEAUX INDICATEURS POUR SIGNAUX RAPIDES (SCALPING)
        try:
            import config
            rsi_period = getattr(config, 'RSI_PERIOD', 7)
            stoch_period = getattr(config, 'STOCHASTIC_PERIOD', 7)
            williams_period = getattr(config, 'WILLIAMS_R_PERIOD', 7)
            cci_period = getattr(config, 'CCI_PERIOD', 10)
        except:
            rsi_period = 7
            stoch_period = 7
            williams_period = 7
            cci_period = 10
        
        stochastic = self.calculate_stochastic(self.candles, stoch_period)
        williams_r = self.calculate_williams_r(self.candles, williams_period)
        cci = self.calculate_cci(self.candles, cci_period)
        price_action = self.detect_price_action_signals(self.candles, self.current_price)
        
        # 8. INDICATEURS SCALPING AVANCÉS
        vwap = self.calculate_vwap(self.candles)
        # Order Flow Delta (nécessite des trades - sera calculé si disponible)
        order_flow_delta = {'delta': 0, 'delta_percent': 0}  # Par défaut
        cumulative_delta = {'cumulative_delta': 0, 'delta_trend': 'neutral'}
        
        # Order flow (existant)
        order_flow = 0
        if self.order_book.get('bids') and self.order_book.get('asks'):
            order_flow = self.calculate_order_flow_imbalance(
                self.order_book['bids'],
                self.order_book['asks']
            )
        
        # Génération du signal amélioré avec toutes les nouvelles données
        signal, signal_details = self.generate_advanced_trading_signal(
            rsi, macd, ema20, ema50, self.current_price,
            bollinger, order_flow, order_book_analysis,
            volatility_regime, key_levels, candlestick_patterns,
            divergence, momentum, stochastic, williams_r, cci, price_action
        )
        
        # Récupérer les frais Hyperliquid
        fees = self.get_hyperliquid_fees()
        
        # Calcul des niveaux de Stop Loss et Take Profit (avec frais) - SCALPING
        sl_tp = self.calculate_sl_tp(
            signal, self.current_price, bollinger, 
            volume_profile, ema20, ema50, rsi, atr, fees
        )
        
        # Calculer le score de qualité du signal
        analysis_dict = {
            'signal': signal,
            'signal_details': signal_details,
            'current_price': self.current_price,
            'candles': self.candles,
            'indicators': {'atr': atr},
            'spread': order_book_analysis.get('spread_percent', 0.1),
            'advanced_analysis': {
                'key_levels': key_levels,
                'order_book': order_book_analysis,
                'momentum': momentum
            }
        }
        signal_quality = self._calculate_signal_quality(analysis_dict)
        
        # Vérifier si on doit entrer dans le trade
        should_enter, enter_reason = self.should_enter_trade(analysis_dict)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'coin': self.coin,
            'interval': self.interval,
            'current_price': self.current_price,
            'signal': signal,
            'signal_details': signal_details,
            'sl_tp': sl_tp,
            'indicators': {
                'rsi': round(rsi, 2),
                'macd': {
                    'value': round(macd['value'], 4),
                    'signal': round(macd['signal'], 4),
                    'histogram': round(macd['histogram'], 4)
                },
                'ema20': round(ema20, 2),
                'ema50': round(ema50, 2),
                'bollinger_bands': {
                    'upper': round(bollinger['upper'], 2),
                    'middle': round(bollinger['middle'], 2),
                    'lower': round(bollinger['lower'], 2)
                },
                'volume_profile': {
                    'poc': round(volume_profile['poc'], 2),
                    'vah': round(volume_profile['vah'], 2),
                    'val': round(volume_profile['val'], 2)
                },
                'order_flow_imbalance': round(order_flow, 2),
                'atr': round(atr, 2),
                'momentum': momentum,
                'stochastic': stochastic,
                'williams_r': williams_r,
                'cci': round(cci, 2),
                'vwap': round(vwap, 2),
                'order_flow_delta': order_flow_delta,
                'cumulative_delta': cumulative_delta,
                'fees': fees
            },
            'signal_quality': round(signal_quality, 1),
            'should_enter_trade': should_enter,
            'enter_reason': enter_reason,
            'advanced_analysis': {
                'order_book': order_book_analysis,
                'volatility': volatility_regime,
                'key_levels': key_levels,
                'candlestick_patterns': candlestick_patterns,
                'divergence': divergence,
                'momentum': momentum,
                'stochastic': stochastic,
                'williams_r': williams_r,
                'cci': cci,
                'price_action': price_action
            },
            'candles_count': len(self.candles),
            'candles': self.candles[-50:] if len(self.candles) >= 50 else self.candles
        }
    
    def generate_advanced_trading_signal(
        self,
        rsi: float,
        macd: Dict[str, float],
        ema20: float,
        ema50: float,
        price: float,
        bollinger: Dict[str, float],
        order_flow: float,
        order_book_analysis: Dict,
        volatility_regime: Dict,
        key_levels: Dict,
        candlestick_patterns: List[Dict],
        divergence: Optional[Dict],
        momentum: Dict,
        stochastic: Dict,
        williams_r: float,
        cci: float,
        price_action: List[Dict]
    ) -> Tuple[str, Dict]:
        """Génère un signal de trading avancé avec toutes les nouvelles fonctionnalités"""
        buy_signals = 0
        sell_signals = 0
        reasons = []
        scalping_signals = []  # Signaux spécifiques au scalping
        
        # SIGNaux de base (existant)
        # RSI
        if rsi < 30:
            buy_signals += 2
            reasons.append("RSI < 30 (survendu)")
        elif rsi < 40:
            buy_signals += 1
            reasons.append("RSI < 40 (légèrement survendu)")
        elif rsi > 70:
            sell_signals += 2
            reasons.append("RSI > 70 (suracheté)")
        elif rsi > 60:
            sell_signals += 1
            reasons.append("RSI > 60 (légèrement suracheté)")
        
        # MACD
        if macd['histogram'] > 0 and macd['value'] > macd['signal']:
            buy_signals += 1
            reasons.append("MACD haussier (histogramme positif)")
        elif macd['histogram'] < 0 and macd['value'] < macd['signal']:
            sell_signals += 1
            reasons.append("MACD baissier (histogramme négatif)")
        
        # EMA Crossover
        if ema20 > ema50:
            buy_signals += 1
            reasons.append("EMA 20 > EMA 50 (Golden Cross)")
        elif ema20 < ema50:
            sell_signals += 1
            reasons.append("EMA 20 < EMA 50 (Death Cross)")
        
        # Prix vs EMA
        if price > ema20 and price > ema50:
            buy_signals += 1
            reasons.append("Prix au-dessus des EMA 20 et 50")
        elif price < ema20 and price < ema50:
            sell_signals += 1
            reasons.append("Prix en-dessous des EMA 20 et 50")
        
        # Bollinger Bands
        if price < bollinger['lower']:
            buy_signals += 1
            reasons.append("Prix en-dessous de la bande inférieure BB (rebond possible)")
        elif price > bollinger['upper']:
            sell_signals += 1
            reasons.append("Prix au-dessus de la bande supérieure BB (retournement possible)")
        
        # Order Flow
        if order_flow > 10:
            buy_signals += 1
            reasons.append(f"Order flow positif ({order_flow:.1f}%) - pression d'achat")
        elif order_flow < -10:
            sell_signals += 1
            reasons.append(f"Order flow négatif ({order_flow:.1f}%) - pression de vente")
        
        # NOUVELLES ANALYSES AVANCÉES
        
        # 1. Analyse du carnet d'ordres (murs et zones de liquidité)
        if order_book_analysis.get('wall_detected'):
            wall_side = order_book_analysis.get('wall_side')
            wall_price = order_book_analysis.get('wall_price', 0)
            if wall_side == 'support' and price <= wall_price * 1.002:  # Prix proche du mur de support
                buy_signals += 2
                scalping_signals.append(f"🛡️ Mur de support détecté à ${wall_price:,.2f}")
                reasons.append(f"Mur de support proche (${wall_price:,.2f}) - rebond probable")
            elif wall_side == 'resistance' and price >= wall_price * 0.998:  # Prix proche du mur de résistance
                sell_signals += 2
                scalping_signals.append(f"🚧 Mur de résistance détecté à ${wall_price:,.2f}")
                reasons.append(f"Mur de résistance proche (${wall_price:,.2f}) - rejet probable")
        
        # Déséquilibre du carnet d'ordres
        ob_imbalance = order_book_analysis.get('order_book_imbalance', 0)
        if ob_imbalance > 15:
            buy_signals += 1
            reasons.append(f"Déséquilibre fort du carnet d'ordres ({ob_imbalance:.1f}% en faveur des achats)")
        elif ob_imbalance < -15:
            sell_signals += 1
            reasons.append(f"Déséquilibre fort du carnet d'ordres ({abs(ob_imbalance):.1f}% en faveur des ventes)")
        
        # 2. Volatilité et squeeze
        if volatility_regime.get('squeeze'):
            scalping_signals.append("⚡ SQUEEZE détecté - Breakout imminent!")
            reasons.append("Squeeze de volatilité - potentiel breakout majeur")
        
        if volatility_regime.get('regime') == 'high':
            scalping_signals.append("📊 Volatilité élevée - opportunités de scalping")
            reasons.append("Régime de haute volatilité - mouvements rapides attendus")
        elif volatility_regime.get('regime') == 'low':
            reasons.append("Régime de faible volatilité - consolidation")
        
        # 3. Niveaux clés et pivot points
        pivot = key_levels.get('pivot_points', {}).get('pivot', 0)
        if pivot > 0:
            if price < pivot * 1.001 and price > pivot * 0.999:  # Prix très proche du pivot
                reasons.append(f"Prix au niveau pivot (${pivot:,.2f}) - zone critique")
        
        # Support proche
        supports = key_levels.get('supports', [])
        for support in supports[:2]:  # Top 2 supports
            if price <= support * 1.002 and price >= support * 0.998:
                buy_signals += 1
                scalping_signals.append(f"📈 Support clé à ${support:,.2f}")
                reasons.append(f"Prix au niveau de support clé (${support:,.2f})")
        
        # Résistance proche
        resistances = key_levels.get('resistances', [])
        for resistance in resistances[:2]:  # Top 2 résistances
            if price >= resistance * 0.998 and price <= resistance * 1.002:
                sell_signals += 1
                scalping_signals.append(f"📉 Résistance clé à ${resistance:,.2f}")
                reasons.append(f"Prix au niveau de résistance clé (${resistance:,.2f})")
        
        # 4. Patterns de chandeliers
        for pattern in candlestick_patterns:
            if pattern.get('signal') == 'BUY':
                buy_signals += 2 if pattern.get('strength') == 'strong' else 1
                scalping_signals.append(f"🕯️ {pattern.get('pattern')} - {pattern.get('description')}")
                reasons.append(f"Pattern {pattern.get('pattern')}: {pattern.get('description')}")
            elif pattern.get('signal') == 'SELL':
                sell_signals += 2 if pattern.get('strength') == 'strong' else 1
                scalping_signals.append(f"🕯️ {pattern.get('pattern')} - {pattern.get('description')}")
                reasons.append(f"Pattern {pattern.get('pattern')}: {pattern.get('description')}")
        
        # 5. Divergences (signaux très forts)
        if divergence:
            if divergence.get('signal') == 'BUY':
                buy_signals += 3
                scalping_signals.append(f"🔄 {divergence.get('description')}")
                reasons.append(f"⚠️ DIVERGENCE HAUSSIÈRE: {divergence.get('description')}")
            elif divergence.get('signal') == 'SELL':
                sell_signals += 3
                scalping_signals.append(f"🔄 {divergence.get('description')}")
                reasons.append(f"⚠️ DIVERGENCE BAISSIÈRE: {divergence.get('description')}")
        
        # 6. Momentum et micro-structure
        momentum_percent = momentum.get('momentum_percent', 0)
        velocity = momentum.get('velocity', 0)
        acceleration = momentum.get('acceleration', 0)
        
        if momentum_percent > 0.5 and velocity > 0.1:
            buy_signals += 1
            reasons.append(f"Momentum haussier fort ({momentum_percent:.2f}%)")
        elif momentum_percent < -0.5 and velocity < -0.1:
            sell_signals += 1
            reasons.append(f"Momentum baissier fort ({abs(momentum_percent):.2f}%)")
        
        if acceleration > 0.05:
            buy_signals += 1
            scalping_signals.append("🚀 Accélération haussière - momentum croissant")
            reasons.append("Accélération du mouvement haussier")
        elif acceleration < -0.05:
            sell_signals += 1
            scalping_signals.append("📉 Accélération baissière - momentum croissant")
            reasons.append("Accélération du mouvement baissier")
        
        # 7. NOUVEAUX INDICATEURS RAPIDES
        
        # Stochastic Oscillator
        if stochastic['k'] < 20 and stochastic['d'] < 20:
            buy_signals += 2
            scalping_signals.append("📊 Stochastic survendu (K < 20, D < 20)")
            reasons.append(f"Stochastic survendu (K: {stochastic['k']:.1f}, D: {stochastic['d']:.1f})")
        elif stochastic['k'] > 80 and stochastic['d'] > 80:
            sell_signals += 2
            scalping_signals.append("📊 Stochastic suracheté (K > 80, D > 80)")
            reasons.append(f"Stochastic suracheté (K: {stochastic['k']:.1f}, D: {stochastic['d']:.1f})")
        elif stochastic['k'] > stochastic['d'] and stochastic['k'] < 50:
            buy_signals += 1
            reasons.append("Stochastic croisement haussier")
        elif stochastic['k'] < stochastic['d'] and stochastic['k'] > 50:
            sell_signals += 1
            reasons.append("Stochastic croisement baissier")
        
        # Williams %R
        if williams_r < -80:
            buy_signals += 2
            scalping_signals.append(f"📈 Williams %R survendu ({williams_r:.1f})")
            reasons.append(f"Williams %R survendu ({williams_r:.1f})")
        elif williams_r > -20:
            sell_signals += 2
            scalping_signals.append(f"📉 Williams %R suracheté ({williams_r:.1f})")
            reasons.append(f"Williams %R suracheté ({williams_r:.1f})")
        
        # CCI (Commodity Channel Index)
        if cci < -100:
            buy_signals += 1
            reasons.append(f"CCI survendu ({cci:.1f})")
        elif cci > 100:
            sell_signals += 1
            reasons.append(f"CCI suracheté ({cci:.1f})")
        elif cci > 0 and cci < 50:
            buy_signals += 1
            reasons.append(f"CCI haussier ({cci:.1f})")
        elif cci < 0 and cci > -50:
            sell_signals += 1
            reasons.append(f"CCI baissier ({cci:.1f})")
        
        # Price Action Signals (très rapides)
        for pa_signal in price_action:
            if pa_signal.get('signal') == 'BUY':
                buy_signals += 2 if pa_signal.get('strength') == 'strong' else 1
                scalping_signals.append(f"⚡ {pa_signal.get('description')}")
                reasons.append(f"Price Action: {pa_signal.get('description')}")
            elif pa_signal.get('signal') == 'SELL':
                sell_signals += 2 if pa_signal.get('strength') == 'strong' else 1
                scalping_signals.append(f"⚡ {pa_signal.get('description')}")
                reasons.append(f"Price Action: {pa_signal.get('description')}")
        
        # Détermination du signal final (seuil abaissé pour plus de signaux)
        # Si différence >= 1, on génère un signal (au lieu de >= 2)
        if buy_signals > sell_signals:
            signal = "ACHAT"
            strength = min(buy_signals / 12.0, 1.0)  # Normaliser sur 12 (plus de signaux possibles)
        elif sell_signals > buy_signals:
            signal = "VENTE"
            strength = min(sell_signals / 12.0, 1.0)
        else:
            signal = "NEUTRE"
            strength = 0.5
        
        return signal, {
            'strength': strength,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'reasons': reasons,
            'scalping_signals': scalping_signals,
            'confidence': 'high' if abs(buy_signals - sell_signals) >= 3 else 'medium' if abs(buy_signals - sell_signals) >= 2 else 'low'
        }
    
    def print_signal(self, analysis: Dict, compact: bool = False):
        """Affiche le signal de manière formatée"""
        if 'error' in analysis:
            print(f"❌ Erreur: {analysis['error']}")
            return
        
        if compact:
            # Version compacte pour le monitoring
            signal = analysis['signal']
            price = analysis['current_price']
            rsi = analysis['indicators']['rsi']
            strength = analysis['signal_details']['strength'] * 100
            
            signal_emoji = "📈" if signal == "ACHAT" else "📉" if signal == "VENTE" else "⚖️"
            print(f"{signal_emoji} [{analysis['timestamp'][:19]}] {signal} | Prix: ${price:,.2f} | RSI: {rsi:.1f} | Force: {strength:.0f}%")
            return
        
        print("\n" + "="*70)
        print(f"🎯 SIGNAL DE TRADING - {analysis['coin']}/{analysis['interval']}")
        print("="*70)
        print(f"⏰ Heure: {analysis['timestamp']}")
        print(f"💰 Prix actuel: ${analysis['current_price']:,.2f}")
        print(f"📊 Chandeliers analysés: {analysis['candles_count']}")
        print()
        
        # Signal principal
        signal = analysis['signal']
        strength = analysis['signal_details']['strength']
        strength_bar = "█" * int(strength * 10)
        
        if signal == "ACHAT":
            print(f"📈 SIGNAL: {signal} (Force: {strength*100:.0f}%) {strength_bar}")
        elif signal == "VENTE":
            print(f"📉 SIGNAL: {signal} (Force: {strength*100:.0f}%) {strength_bar}")
        else:
            print(f"⚖️  SIGNAL: {signal}")
        
        print(f"   Signaux d'achat: {analysis['signal_details']['buy_signals']}")
        print(f"   Signaux de vente: {analysis['signal_details']['sell_signals']}")
        print()
        
        # Raisons
        if analysis['signal_details']['reasons']:
            print("📋 Raisons du signal:")
            for reason in analysis['signal_details']['reasons']:
                print(f"   • {reason}")
        print()
        
        # Indicateurs
        ind = analysis['indicators']
        print("📊 Indicateurs techniques:")
        print(f"   RSI (14): {ind['rsi']:.2f} ", end="")
        if ind['rsi'] < 30:
            print("(Survendu)")
        elif ind['rsi'] > 70:
            print("(Suracheté)")
        else:
            print("(Normal)")
        
        print(f"   MACD Histogram: {ind['macd']['histogram']:.4f} ", end="")
        print("(Haussier)" if ind['macd']['histogram'] > 0 else "(Baissier)")
        
        print(f"   EMA 20: ${ind['ema20']:,.2f}")
        print(f"   EMA 50: ${ind['ema50']:,.2f}")
        print(f"   Position: ", end="")
        if analysis['current_price'] > ind['ema20'] and analysis['current_price'] > ind['ema50']:
            print("Au-dessus des EMA")
        elif analysis['current_price'] < ind['ema20'] and analysis['current_price'] < ind['ema50']:
            print("En-dessous des EMA")
        else:
            print("Entre les EMA")
        
        print(f"   Bollinger Bands:")
        print(f"      Haut: ${ind['bollinger_bands']['upper']:,.2f}")
        print(f"      Milieu: ${ind['bollinger_bands']['middle']:,.2f}")
        print(f"      Bas: ${ind['bollinger_bands']['lower']:,.2f}")
        
        print(f"   Volume Profile:")
        print(f"      POC: ${ind['volume_profile']['poc']:,.2f}")
        print(f"      VAH: ${ind['volume_profile']['vah']:,.2f}")
        print(f"      VAL: ${ind['volume_profile']['val']:,.2f}")
        
        print(f"   Order Flow Imbalance: {ind['order_flow_imbalance']:.2f}%")
        
        # Nouvelles fonctionnalités avancées
        if 'advanced_analysis' in analysis:
            adv = analysis['advanced_analysis']
            print()
            print("🔬 ANALYSE AVANCÉE (Scalping):")
            
            # Volatilité
            if 'volatility' in adv:
                vol = adv['volatility']
                regime_emoji = "📊" if vol.get('regime') == 'high' else "📉" if vol.get('regime') == 'low' else "➡️"
                print(f"   {regime_emoji} Volatilité: {vol.get('regime', 'unknown').upper()} ({vol.get('volatility_percent', 0):.3f}%)")
                if vol.get('squeeze'):
                    print(f"   ⚡ SQUEEZE détecté - Breakout imminent!")
                if 'atr_value' in vol:
                    print(f"   ATR: ${vol['atr_value']:,.2f}")
            
            # Order Book Analysis
            if 'order_book' in adv:
                ob = adv['order_book']
                if ob.get('wall_detected'):
                    wall_side_emoji = "🛡️" if ob.get('wall_side') == 'support' else "🚧"
                    print(f"   {wall_side_emoji} Mur détecté: {ob.get('wall_side', 'unknown')} à ${ob.get('wall_price', 0):,.2f}")
                if ob.get('support_levels'):
                    print(f"   📈 Supports: {', '.join([f'${s:,.0f}' for s in ob['support_levels'][:3]])}")
                if ob.get('resistance_levels'):
                    print(f"   📉 Résistances: {', '.join([f'${r:,.0f}' for r in ob['resistance_levels'][:3]])}")
            
            # Niveaux clés
            if 'key_levels' in adv:
                kl = adv['key_levels']
                if kl.get('pivot_points', {}).get('pivot'):
                    pivot = kl['pivot_points']['pivot']
                    print(f"   ⚖️ Pivot: ${pivot:,.2f}")
                if kl.get('supports'):
                    print(f"   📈 Supports techniques: {', '.join([f'${s:,.0f}' for s in kl['supports'][:3]])}")
                if kl.get('resistances'):
                    print(f"   📉 Résistances techniques: {', '.join([f'${r:,.0f}' for r in kl['resistances'][:3]])}")
            
            # Patterns de chandeliers
            if 'candlestick_patterns' in adv and adv['candlestick_patterns']:
                print(f"   🕯️ Patterns détectés:")
                for pattern in adv['candlestick_patterns']:
                    signal_emoji = "📈" if pattern.get('signal') == 'BUY' else "📉" if pattern.get('signal') == 'SELL' else "⚖️"
                    print(f"      {signal_emoji} {pattern.get('pattern')}: {pattern.get('description')}")
            
            # Divergence
            if 'divergence' in adv and adv['divergence']:
                div = adv['divergence']
                div_emoji = "📈" if div.get('signal') == 'BUY' else "📉"
                print(f"   {div_emoji} ⚠️ DIVERGENCE: {div.get('description', '')}")
            
            # Momentum
            if 'momentum' in adv:
                mom = adv['momentum']
                if mom.get('momentum_percent', 0) != 0:
                    print(f"   🚀 Momentum: {mom.get('momentum_percent', 0):.3f}% | Vitesse: {mom.get('velocity', 0):.3f}% | Accélération: {mom.get('acceleration', 0):.3f}%")
        
        # Signaux de scalping
        if 'signal_details' in analysis and 'scalping_signals' in analysis['signal_details']:
            scalping = analysis['signal_details']['scalping_signals']
            if scalping:
                print()
                print("⚡ SIGNAUX DE SCALPING:")
                for sig in scalping:
                    print(f"   • {sig}")
        
        # Confiance
        if 'signal_details' in analysis and 'confidence' in analysis['signal_details']:
            conf = analysis['signal_details']['confidence']
            conf_emoji = "🟢" if conf == 'high' else "🟡" if conf == 'medium' else "🔴"
            print()
            print(f"   {conf_emoji} Confiance: {conf.upper()}")
        
        # SL/TP
        if 'sl_tp' in analysis and analysis['sl_tp']['stop_loss'] > 0:
            sl_tp = analysis['sl_tp']
            print()
            print("🛡️  Gestion du Risque:")
            if analysis['signal'] == "ACHAT":
                print(f"   Stop Loss: ${sl_tp['stop_loss']:,.2f} (-{sl_tp['stop_loss_percent']:.2f}%)")
                print(f"   Take Profit: ${sl_tp['take_profit']:,.2f} (+{sl_tp['take_profit_percent']:.2f}%)")
            else:
                print(f"   Stop Loss: ${sl_tp['stop_loss']:,.2f} (+{sl_tp['stop_loss_percent']:.2f}%)")
                print(f"   Take Profit: ${sl_tp['take_profit']:,.2f} (-{sl_tp['take_profit_percent']:.2f}%)")
            print(f"   Risk/Reward: 1:{sl_tp['risk_reward']:.2f}")
        
        print("="*70 + "\n")
    
    def monitor(self, interval_seconds: int = 60, compact: bool = True):
        """Surveille le marché en continu et génère des signaux"""
        print(f"\n🔄 Surveillance en continu activée (intervalle: {interval_seconds}s)")
        print("Appuyez sur Ctrl+C pour arrêter\n")
        
        last_signal = None
        
        try:
            while True:
                # Recharger les données
                self.fetch_historical_candles(limit=200)
                
                # Analyser
                analysis = self.analyze()
                
                # Afficher seulement si le signal a changé ou toutes les 5 minutes
                current_signal = analysis.get('signal')
                if current_signal != last_signal or not compact:
                    if compact:
                        self.print_signal(analysis, compact=True)
                    else:
                        self.print_signal(analysis, compact=False)
                    last_signal = current_signal
                
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            print("\n\n⏹️  Surveillance arrêtée par l'utilisateur")


def main():
    """Fonction principale pour générer des signaux"""
    import sys
    
    print("🚀 Système de Signaux de Trading Hyperliquid")
    print("=" * 70)
    
    # Configuration
    coin = "BTC"
    interval = "5m"  # Options: 1m, 5m, 15m, 1h, 4h, 1d
    monitor_mode = "--monitor" in sys.argv or "-m" in sys.argv
    interval_seconds = 60
    
    # Parser les arguments pour l'intervalle de monitoring
    if "--interval" in sys.argv:
        idx = sys.argv.index("--interval")
        if idx + 1 < len(sys.argv):
            try:
                interval_seconds = int(sys.argv[idx + 1])
            except ValueError:
                print("⚠️  Intervalle invalide, utilisation de 60s par défaut")
    
    generator = HyperliquidSignalGenerator(coin=coin, interval=interval)
    
    # Charger les données historiques
    print(f"\n📥 Chargement des données historiques pour {coin} ({interval})...")
    candles = generator.fetch_historical_candles(limit=200)
    
    if not candles:
        print("❌ Impossible de charger les données historiques")
        return
    
    print(f"✅ {len(candles)} chandeliers chargés")
    
    # Effectuer l'analyse
    analysis = generator.analyze()
    generator.print_signal(analysis)
    
    # Mode monitoring si demandé
    if monitor_mode:
        generator.monitor(interval_seconds=interval_seconds, compact=True)
    else:
        print("\n💡 Pour surveiller en continu, utilisez:")
        print("   python hyperliquid_signals.py --monitor")
        print("   ou")
        print("   python hyperliquid_signals.py -m --interval 30  # toutes les 30 secondes")


if __name__ == "__main__":
    main()

