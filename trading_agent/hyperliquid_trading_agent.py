"""
Agent de Trading Automatisé pour Hyperliquid
Se connecte aux signaux générés et exécute les trades automatiquement
"""

import sys
import os
import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from decimal import Decimal, ROUND_DOWN
import requests
from eth_account import Account
from eth_account.messages import encode_defunct
import web3

# Configuration de l'encodage UTF-8 pour Windows
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

try:
    # Ajouter le dossier parent au path pour les imports
    import sys
    import os
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    import config
    from hyperliquid_signals import HyperliquidSignalGenerator
except ImportError as e:
    logger.error(f"Erreur d'import: {e}")
    logger.error("Assurez-vous que config.py et hyperliquid_signals.py sont dans le dossier parent")
    sys.exit(1)


class HyperliquidTradingAgent:
    """Agent de trading automatisé pour Hyperliquid"""
    
    def __init__(self, wallet_address: str = None, private_key: str = None):
        """
        Initialise l'agent de trading
        
        Args:
            wallet_address: Adresse du wallet Hyperliquid
            private_key: Clé privée (ou depuis variable d'environnement HYPERLIQUID_PRIVATE_KEY)
        """
        # Configuration API
        self.api_url = "https://api.hyperliquid.xyz/info"
        self.exchange_url = "https://api.hyperliquid.xyz/exchange"
        
        # Charger les clés API
        self.wallet_address = wallet_address or config.HYPERLIQUID_API.get('wallet_address', '')
        self.private_key = private_key or os.getenv('HYPERLIQUID_PRIVATE_KEY') or config.HYPERLIQUID_API.get('private_key', '')
        
        if not self.wallet_address or not self.private_key:
            raise ValueError("❌ Wallet address et private key requis. Configurez-les dans config.py ou variables d'environnement")
        
        # Initialiser le compte Ethereum pour la signature
        try:
            self.account = Account.from_key(self.private_key)
            if self.account.address.lower() != self.wallet_address.lower():
                logger.warning(f"⚠️ L'adresse wallet ne correspond pas à la clé privée")
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation du compte: {e}")
            raise
        
        # Générateur de signaux
        self.signal_generator = None
        self.current_coin = config.DEFAULT_COIN
        self.current_interval = config.DEFAULT_INTERVAL
        
        # État de trading
        self.active_positions = {}  # {coin: position_info}
        self.trade_history = []
        self.balance = 0.0
        self.max_position_size = 1000.0  # USD par défaut
        self.max_daily_trades = 50
        self.daily_trade_count = 0
        self.last_trade_date = None
        
        # Configuration de risque
        self.max_slippage = 0.001  # 0.1%
        self.min_confidence = 'medium'  # 'high', 'medium', 'low'
        
        logger.info(f"✅ Agent de trading initialisé pour wallet: {self.wallet_address[:10]}...")
    
    def get_user_state(self) -> Dict:
        """Récupère l'état du compte utilisateur"""
        try:
            response = requests.post(
                self.api_url,
                json={
                    'type': 'clearinghouseState',
                    'user': self.wallet_address
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                logger.error(f"Erreur API: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'état: {e}")
            return {}
    
    def get_balance(self) -> float:
        """Récupère le solde disponible"""
        try:
            state = self.get_user_state()
            if state and 'marginSummary' in state:
                # Calculer le solde disponible
                margin_summary = state['marginSummary']
                self.balance = float(margin_summary.get('accountValue', 0))
                return self.balance
            return 0.0
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du solde: {e}")
            return 0.0
    
    def get_open_positions(self) -> Dict:
        """Récupère les positions ouvertes"""
        try:
            state = self.get_user_state()
            if state and 'assetPositions' in state:
                positions = {}
                for pos in state['assetPositions']:
                    coin = pos.get('position', {}).get('coin', '')
                    if coin:
                        positions[coin] = {
                            'size': float(pos.get('position', {}).get('szi', 0)),
                            'entry_price': float(pos.get('position', {}).get('entryPx', 0)),
                            'unrealized_pnl': float(pos.get('position', {}).get('unrealizedPnl', 0)),
                            'leverage': float(pos.get('position', {}).get('leverage', {}).get('value', 1))
                        }
                self.active_positions = positions
                return positions
            return {}
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des positions: {e}")
            return {}
    
    def calculate_position_size(self, signal_strength: float, confidence: str, balance: float) -> float:
        """Calcule la taille de position basée sur le risque"""
        # Taille de base
        base_size = self.max_position_size
        
        # Ajuster selon la force du signal
        if signal_strength > 0.8:
            size_multiplier = 1.0
        elif signal_strength > 0.6:
            size_multiplier = 0.75
        elif signal_strength > 0.4:
            size_multiplier = 0.5
        else:
            size_multiplier = 0.25
        
        # Ajuster selon la confiance
        if confidence == 'high':
            confidence_multiplier = 1.0
        elif confidence == 'medium':
            confidence_multiplier = 0.75
        else:
            confidence_multiplier = 0.5
        
        # Calculer la taille finale
        position_size = base_size * size_multiplier * confidence_multiplier
        
        # Limiter à 10% du solde maximum
        max_from_balance = balance * 0.10
        position_size = min(position_size, max_from_balance)
        
        return round(position_size, 2)
    
    def place_order(
        self,
        coin: str,
        side: str,  # 'B' pour buy, 'A' pour sell
        size: float,
        price: Optional[float] = None,
        order_type: str = 'Market',  # 'Market', 'Limit'
        reduce_only: bool = False
    ) -> Dict:
        """
        Place un ordre sur Hyperliquid
        
        Args:
            coin: Symbole de la crypto (ex: 'BTC')
            side: 'B' pour achat, 'A' pour vente
            size: Taille de l'ordre
            price: Prix limite (si order_type='Limit')
            order_type: Type d'ordre ('Market' ou 'Limit')
            reduce_only: Si True, réduit seulement une position existante
        """
        try:
            # Vérifier le solde
            balance = self.get_balance()
            if balance < size and side == 'B':
                logger.warning(f"❌ Solde insuffisant: {balance} < {size}")
                return {'status': 'error', 'message': 'Solde insuffisant'}
            
            # Préparer l'ordre
            order = {
                'a': int(size * 1e6),  # Taille en micro-units
                'b': side == 'B',  # True pour buy, False pour sell
                'p': str(price) if price else None,
                'r': reduce_only,
                's': coin,
                't': {'limit': {'tif': 'Ioc'}} if order_type == 'Limit' else {'market': {}},
            }
            
            # Créer le payload pour la signature
            timestamp = int(time.time() * 1000)
            payload = {
                'action': {'type': 'order', 'orders': [order], 'grouping': 'na'},
                'nonce': timestamp,
                'vaultAddress': None
            }
            
            # Signer la transaction
            message = json.dumps(payload, separators=(',', ':'))
            message_hash = encode_defunct(text=message)
            signed_message = self.account.sign_message(message_hash)
            
            # Préparer la requête
            headers = {
                'Content-Type': 'application/json'
            }
            
            request_data = {
                'action': payload['action'],
                'nonce': payload['nonce'],
                'signature': {
                    'r': hex(signed_message.signature.r),
                    's': hex(signed_message.signature.s),
                    'v': signed_message.signature.v
                },
                'vaultAddress': None
            }
            
            # Envoyer l'ordre
            response = requests.post(
                self.exchange_url,
                json=request_data,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'ok':
                    logger.info(f"✅ Ordre placé: {side} {size} {coin} @ {price if price else 'Market'}")
                    return {'status': 'success', 'data': result}
                else:
                    logger.error(f"❌ Erreur ordre: {result.get('response', {}).get('data', 'Unknown error')}")
                    return {'status': 'error', 'message': result.get('response', {}).get('data', 'Unknown error')}
            else:
                logger.error(f"❌ Erreur HTTP: {response.status_code}")
                return {'status': 'error', 'message': f'HTTP {response.status_code}'}
                
        except Exception as e:
            logger.error(f"❌ Erreur lors du placement de l'ordre: {e}", exc_info=True)
            return {'status': 'error', 'message': str(e)}
    
    def place_stop_loss(self, coin: str, stop_price: float, size: float) -> Dict:
        """Place un ordre Stop Loss"""
        try:
            # Hyperliquid utilise des ordres stop via l'API
            # Pour simplifier, on utilise un ordre limite avec reduce_only
            side = 'A'  # Vendre pour fermer une position long
            
            return self.place_order(
                coin=coin,
                side=side,
                size=size,
                price=stop_price,
                order_type='Limit',
                reduce_only=True
            )
        except Exception as e:
            logger.error(f"Erreur lors du placement du Stop Loss: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def place_take_profit(self, coin: str, tp_price: float, size: float) -> Dict:
        """Place un ordre Take Profit"""
        try:
            side = 'A'  # Vendre pour fermer une position long
            
            return self.place_order(
                coin=coin,
                side=side,
                size=size,
                price=tp_price,
                order_type='Limit',
                reduce_only=True
            )
        except Exception as e:
            logger.error(f"Erreur lors du placement du Take Profit: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def execute_trade(self, analysis: Dict) -> Dict:
        """
        Exécute un trade basé sur l'analyse
        
        Args:
            analysis: Résultat de l'analyse du signal generator
        """
        try:
            signal = analysis.get('signal')
            if signal == 'NEUTRE':
                logger.debug("Signal NEUTRE - Pas de trade")
                return {'status': 'skipped', 'reason': 'Signal neutre'}
            
            # Vérifier la confiance
            confidence = analysis.get('signal_details', {}).get('confidence', 'low')
            if confidence == 'low' and self.min_confidence == 'high':
                logger.debug(f"Confiance trop faible: {confidence}")
                return {'status': 'skipped', 'reason': f'Confiance trop faible: {confidence}'}
            
            # Vérifier les limites quotidiennes
            today = datetime.now().date()
            if self.last_trade_date != today:
                self.daily_trade_count = 0
                self.last_trade_date = today
            
            if self.daily_trade_count >= self.max_daily_trades:
                logger.warning(f"Limite quotidienne atteinte: {self.max_daily_trades} trades")
                return {'status': 'skipped', 'reason': 'Limite quotidienne atteinte'}
            
            coin = analysis.get('coin', self.current_coin)
            current_price = analysis.get('current_price', 0)
            sl_tp = analysis.get('sl_tp', {})
            
            if not sl_tp or sl_tp.get('stop_loss', 0) == 0:
                logger.warning("SL/TP non calculés - Pas de trade")
                return {'status': 'skipped', 'reason': 'SL/TP non calculés'}
            
            # Vérifier les positions existantes
            open_positions = self.get_open_positions()
            if coin in open_positions:
                logger.info(f"Position existante pour {coin} - Vérification si fermeture nécessaire")
                # Logique de gestion de position existante (à implémenter)
                return {'status': 'skipped', 'reason': 'Position existante'}
            
            # Calculer la taille de position
            balance = self.get_balance()
            signal_strength = analysis.get('signal_details', {}).get('strength', 0.5)
            position_size = self.calculate_position_size(signal_strength, confidence, balance)
            
            if position_size < 10:  # Minimum 10 USD
                logger.warning(f"Taille de position trop petite: {position_size} USD")
                return {'status': 'skipped', 'reason': 'Position trop petite'}
            
            # Placer l'ordre
            side = 'B' if signal == 'ACHAT' else 'A'
            order_result = self.place_order(
                coin=coin,
                side=side,
                size=position_size,
                order_type='Market'
            )
            
            if order_result.get('status') == 'success':
                # Placer les ordres SL/TP
                stop_loss = sl_tp.get('stop_loss', 0)
                take_profit = sl_tp.get('take_profit', 0)
                
                if stop_loss > 0:
                    self.place_stop_loss(coin, stop_loss, position_size)
                
                if take_profit > 0:
                    self.place_take_profit(coin, take_profit, position_size)
                
                # Enregistrer le trade
                trade_record = {
                    'timestamp': datetime.now().isoformat(),
                    'coin': coin,
                    'side': side,
                    'size': position_size,
                    'entry_price': current_price,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'signal_strength': signal_strength,
                    'confidence': confidence,
                    'analysis': analysis
                }
                self.trade_history.append(trade_record)
                self.daily_trade_count += 1
                
                logger.info(f"✅ Trade exécuté: {side} {position_size} {coin} @ {current_price}")
                logger.info(f"   SL: {stop_loss} | TP: {take_profit}")
                
                return {'status': 'success', 'trade': trade_record}
            else:
                return order_result
                
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'exécution du trade: {e}", exc_info=True)
            return {'status': 'error', 'message': str(e)}
    
    def monitor_and_trade(self, coin: str = None, interval: str = None, check_interval: int = 60):
        """
        Surveille les signaux et exécute les trades automatiquement
        
        Args:
            coin: Crypto à trader (défaut: config.DEFAULT_COIN)
            interval: Intervalle de temps (défaut: config.DEFAULT_INTERVAL)
            check_interval: Intervalle de vérification en secondes
        """
        coin = coin or self.current_coin
        interval = interval or self.current_interval
        
        logger.info(f"🚀 Démarrage du monitoring automatique: {coin}/{interval}")
        logger.info(f"   Vérification toutes les {check_interval} secondes")
        logger.info(f"   Confiance minimum: {self.min_confidence}")
        logger.info(f"   Taille max position: {self.max_position_size} USD")
        
        # Initialiser le générateur de signaux
        self.signal_generator = HyperliquidSignalGenerator(coin=coin, interval=interval)
        self.current_coin = coin
        self.current_interval = interval
        
        try:
            while True:
                try:
                    # Récupérer les données
                    self.signal_generator.fetch_historical_candles(limit=200)
                    
                    # Analyser
                    analysis = self.signal_generator.analyze()
                    
                    if 'error' in analysis:
                        logger.warning(f"Erreur d'analyse: {analysis['error']}")
                        time.sleep(check_interval)
                        continue
                    
                    # Afficher le signal
                    signal = analysis.get('signal', 'NEUTRE')
                    price = analysis.get('current_price', 0)
                    confidence = analysis.get('signal_details', {}).get('confidence', 'low')
                    
                    logger.info(f"📊 Signal: {signal} | Prix: ${price:,.2f} | Confiance: {confidence}")
                    
                    # Exécuter le trade si signal valide
                    if signal != 'NEUTRE':
                        trade_result = self.execute_trade(analysis)
                        logger.info(f"Résultat trade: {trade_result.get('status')}")
                    
                    # Afficher l'état
                    balance = self.get_balance()
                    positions = self.get_open_positions()
                    logger.info(f"💰 Solde: ${balance:,.2f} | Positions ouvertes: {len(positions)}")
                    
                except KeyboardInterrupt:
                    logger.info("⏹️ Arrêt demandé par l'utilisateur")
                    break
                except Exception as e:
                    logger.error(f"Erreur dans la boucle de monitoring: {e}", exc_info=True)
                
                time.sleep(check_interval)
                
        except Exception as e:
            logger.error(f"Erreur fatale: {e}", exc_info=True)
    
    def get_trade_statistics(self) -> Dict:
        """Retourne les statistiques de trading"""
        total_trades = len(self.trade_history)
        successful_trades = sum(1 for t in self.trade_history if t.get('status') == 'success')
        
        return {
            'total_trades': total_trades,
            'successful_trades': successful_trades,
            'success_rate': (successful_trades / total_trades * 100) if total_trades > 0 else 0,
            'daily_trades': self.daily_trade_count,
            'active_positions': len(self.active_positions),
            'balance': self.get_balance()
        }


def main():
    """Fonction principale"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Agent de Trading Automatisé Hyperliquid')
    parser.add_argument('--coin', type=str, default=None, help='Crypto à trader (ex: BTC)')
    parser.add_argument('--interval', type=str, default=None, help='Intervalle (ex: 5m)')
    parser.add_argument('--check-interval', type=int, default=60, help='Intervalle de vérification (secondes)')
    parser.add_argument('--max-position', type=float, default=1000, help='Taille max position (USD)')
    parser.add_argument('--min-confidence', type=str, choices=['high', 'medium', 'low'], default='medium')
    
    args = parser.parse_args()
    
    try:
        # Créer l'agent
        agent = HyperliquidTradingAgent()
        
        # Configurer les paramètres
        if args.max_position:
            agent.max_position_size = args.max_position
        if args.min_confidence:
            agent.min_confidence = args.min_confidence
        
        # Démarrer le monitoring
        agent.monitor_and_trade(
            coin=args.coin,
            interval=args.interval,
            check_interval=args.check_interval
        )
        
    except ValueError as e:
        logger.error(f"❌ Erreur de configuration: {e}")
        logger.error("Configurez HYPERLIQUID_PRIVATE_KEY dans les variables d'environnement ou dans config.py")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

