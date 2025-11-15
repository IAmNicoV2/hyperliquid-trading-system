"""
WebSocket Client pour Hyperliquid - Données temps réel
Latence cible : <100ms pour scalping haute fréquence
"""

import asyncio
import json
import time
import logging
from typing import Dict, List, Callable, Optional
from collections import deque
import websocket
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


class HyperliquidWebSocket:
    """Client WebSocket pour Hyperliquid avec reconnexion automatique"""
    
    def __init__(self, on_price_update: Callable = None, on_orderbook_update: Callable = None):
        """
        Initialise le client WebSocket
        
        Args:
            on_price_update: Callback appelé à chaque mise à jour de prix
            on_orderbook_update: Callback appelé à chaque mise à jour de l'order book
        """
        self.ws_url = "wss://api.hyperliquid.xyz/ws"
        self.ws = None
        self.connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 1  # secondes
        
        # Callbacks
        self.on_price_update = on_price_update
        self.on_orderbook_update = on_orderbook_update
        
        # Buffer circulaire pour micro-ticks (100 derniers)
        self.price_buffer = deque(maxlen=100)
        self.orderbook_buffer = deque(maxlen=100)
        
        # Subscriptions
        self.subscribed_coins = set()
        self.subscribed_orderbooks = set()
        
        # Thread de reconnexion
        self.reconnect_thread = None
        self.running = False
        
        # Métriques de performance
        self.last_update_time = 0
        self.latency_samples = deque(maxlen=100)
        
    def _on_message(self, ws, message):
        """Gère les messages WebSocket"""
        try:
            data = json.loads(message)
            timestamp = time.time()
            
            # Calculer la latence
            if self.last_update_time > 0:
                latency = (timestamp - self.last_update_time) * 1000  # ms
                self.latency_samples.append(latency)
            
            self.last_update_time = timestamp
            
            # Traiter selon le type de message
            if 'channel' in data:
                channel = data['channel']
                
                if channel == 'ticker':
                    self._handle_ticker(data)
                elif channel == 'l2Book':
                    self._handle_orderbook(data)
                elif channel == 'trades':
                    self._handle_trades(data)
                    
        except Exception as e:
            logger.error(f"Erreur traitement message WebSocket: {e}", exc_info=True)
    
    def _handle_ticker(self, data: Dict):
        """Gère les mises à jour de ticker (prix)"""
        try:
            if 'data' in data:
                ticker_data = data['data']
                
                # Extraire les informations de prix
                price_update = {
                    'coin': ticker_data.get('coin', ''),
                    'price': float(ticker_data.get('lastPrice', 0)),
                    'bid': float(ticker_data.get('bid', 0)),
                    'ask': float(ticker_data.get('ask', 0)),
                    'volume_24h': float(ticker_data.get('volume24h', 0)),
                    'timestamp': time.time(),
                    'spread': 0
                }
                
                # Calculer le spread
                if ticker_data.get('bid') and ticker_data.get('ask'):
                    bid = float(ticker_data['bid'])
                    ask = float(ticker_data['ask'])
                    if bid > 0:
                        ticker_data['spread'] = ((ask - bid) / bid) * 100
                
                # Ajouter au buffer
                self.price_buffer.append(price_update)
                
                # Appeler le callback
                if self.on_price_update:
                    self.on_price_update(price_update)
                    
        except Exception as e:
            logger.error(f"Erreur traitement ticker: {e}")
    
    def _handle_orderbook(self, data: Dict):
        """Gère les mises à jour de l'order book"""
        try:
            if 'data' in data:
                ob_data = data['data']
                
                orderbook_update = {
                    'coin': ob_data.get('coin', ''),
                    'bids': ob_data.get('bids', []),
                    'asks': ob_data.get('asks', []),
                    'timestamp': time.time()
                }
                
                # Calculer les métriques
                if orderbook_update['bids'] and orderbook_update['asks']:
                    best_bid = float(orderbook_update['bids'][0][0]) if orderbook_update['bids'] else 0
                    best_ask = float(orderbook_update['asks'][0][0]) if orderbook_update['asks'] else 0
                    
                    if best_bid > 0:
                        orderbook_update['spread'] = ((best_ask - best_bid) / best_bid) * 100
                        orderbook_update['spread_abs'] = best_ask - best_bid
                    
                    # Calculer l'imbalance sur 10 premiers niveaux
                    bid_volume = sum(float(b[1]) for b in orderbook_update['bids'][:10])
                    ask_volume = sum(float(a[1]) for a in orderbook_update['asks'][:10])
                    total_volume = bid_volume + ask_volume
                    
                    if total_volume > 0:
                        orderbook_update['imbalance'] = ((bid_volume - ask_volume) / total_volume) * 100
                    else:
                        orderbook_update['imbalance'] = 0
                
                # Ajouter au buffer
                self.orderbook_buffer.append(orderbook_update)
                
                # Appeler le callback
                if self.on_orderbook_update:
                    self.on_orderbook_update(orderbook_update)
                    
        except Exception as e:
            logger.error(f"Erreur traitement orderbook: {e}")
    
    def _handle_trades(self, data: Dict):
        """Gère les trades récents"""
        try:
            if 'data' in data:
                trades = data['data']
                # Utiliser les trades pour calculer order flow delta
                # (sera utilisé dans l'analyse)
                pass
        except Exception as e:
            logger.error(f"Erreur traitement trades: {e}")
    
    def _on_error(self, ws, error):
        """Gère les erreurs WebSocket"""
        logger.error(f"Erreur WebSocket: {error}")
        self.connected = False
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Gère la fermeture de la connexion"""
        logger.warning(f"WebSocket fermé: {close_status_code} - {close_msg}")
        self.connected = False
        
        # Tentative de reconnexion
        if self.running:
            self._reconnect()
    
    def _on_open(self, ws):
        """Gère l'ouverture de la connexion"""
        logger.info("✅ WebSocket connecté à Hyperliquid")
        self.connected = True
        self.reconnect_attempts = 0
        
        # Resubscribe aux coins précédents
        for coin in self.subscribed_coins:
            self.subscribe_ticker(coin)
        
        for coin in self.subscribed_orderbooks:
            self.subscribe_orderbook(coin)
    
    def _reconnect(self):
        """Tente de reconnecter avec backoff exponentiel"""
        if not self.running:
            return
        
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"❌ Impossible de reconnecter après {self.max_reconnect_attempts} tentatives")
            return
        
        self.reconnect_attempts += 1
        delay = min(self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), 60)
        
        logger.info(f"Tentative de reconnexion {self.reconnect_attempts}/{self.max_reconnect_attempts} dans {delay}s...")
        time.sleep(delay)
        
        try:
            self.connect()
        except Exception as e:
            logger.error(f"Erreur reconnexion: {e}")
            if self.running:
                self._reconnect()
    
    def connect(self):
        """Établit la connexion WebSocket"""
        try:
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            
            # Démarrer dans un thread séparé
            def run_ws():
                self.ws.run_forever()
            
            ws_thread = threading.Thread(target=run_ws, daemon=True)
            ws_thread.start()
            
            # Attendre la connexion (max 5 secondes)
            timeout = 5
            start = time.time()
            while not self.connected and (time.time() - start) < timeout:
                time.sleep(0.1)
            
            if not self.connected:
                raise Exception("Timeout lors de la connexion WebSocket")
                
        except Exception as e:
            logger.error(f"Erreur connexion WebSocket: {e}")
            raise
    
    def subscribe_ticker(self, coin: str):
        """S'abonne aux mises à jour de prix pour un coin"""
        if not self.connected:
            logger.warning("WebSocket non connecté, subscription sera effectuée après connexion")
            self.subscribed_coins.add(coin)
            return
        
        try:
            # Format de subscription Hyperliquid
            subscribe_msg = {
                "method": "subscribe",
                "subscription": {
                    "type": "ticker",
                    "coin": coin
                }
            }
            
            if self.ws:
                self.ws.send(json.dumps(subscribe_msg))
                self.subscribed_coins.add(coin)
                logger.info(f"✅ Abonné au ticker: {coin}")
        except Exception as e:
            logger.error(f"Erreur subscription ticker {coin}: {e}")
    
    def subscribe_orderbook(self, coin: str, depth: int = 50):
        """S'abonne aux mises à jour de l'order book pour un coin"""
        if not self.connected:
            logger.warning("WebSocket non connecté, subscription sera effectuée après connexion")
            self.subscribed_orderbooks.add(coin)
            return
        
        try:
            subscribe_msg = {
                "method": "subscribe",
                "subscription": {
                    "type": "l2Book",
                    "coin": coin,
                    "depth": depth
                }
            }
            
            if self.ws:
                self.ws.send(json.dumps(subscribe_msg))
                self.subscribed_orderbooks.add(coin)
                logger.info(f"✅ Abonné à l'order book: {coin} (depth: {depth})")
        except Exception as e:
            logger.error(f"Erreur subscription orderbook {coin}: {e}")
    
    def get_latest_price(self, coin: str) -> Optional[Dict]:
        """Récupère le dernier prix depuis le buffer"""
        for price_data in reversed(self.price_buffer):
            if price_data.get('coin') == coin:
                return price_data
        return None
    
    def get_latest_orderbook(self, coin: str) -> Optional[Dict]:
        """Récupère le dernier order book depuis le buffer"""
        for ob_data in reversed(self.orderbook_buffer):
            if ob_data.get('coin') == coin:
                return ob_data
        return None
    
    def get_average_latency(self) -> float:
        """Retourne la latence moyenne en ms"""
        if not self.latency_samples:
            return 0.0
        return sum(self.latency_samples) / len(self.latency_samples)
    
    def start(self):
        """Démarre le client WebSocket"""
        self.running = True
        self.connect()
    
    def stop(self):
        """Arrête le client WebSocket"""
        self.running = False
        if self.ws:
            self.ws.close()
        self.connected = False
        logger.info("WebSocket arrêté")


# Exemple d'utilisation
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    def on_price(update):
        print(f"Prix {update['coin']}: ${update['price']:.2f} (spread: {update.get('spread', 0):.3f}%)")
    
    def on_orderbook(update):
        print(f"OrderBook {update['coin']}: imbalance {update.get('imbalance', 0):.2f}%")
    
    ws_client = HyperliquidWebSocket(
        on_price_update=on_price,
        on_orderbook_update=on_orderbook
    )
    
    try:
        ws_client.start()
        ws_client.subscribe_ticker("BTC")
        ws_client.subscribe_orderbook("BTC", depth=50)
        
        # Garder le script actif
        while True:
            time.sleep(1)
            latency = ws_client.get_average_latency()
            if latency > 0:
                print(f"Latence moyenne: {latency:.2f}ms")
    except KeyboardInterrupt:
        ws_client.stop()

