"""
Position Manager pour Scalping - Gestion avancée des positions
Money Management, Trailing Stops, Risk Management
"""

import time
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)

try:
    import config
except ImportError:
    logger.warning("config.py non trouvé, utilisation des valeurs par défaut")
    config = None


class PositionManager:
    """Gestionnaire de positions pour scalping haute fréquence"""
    
    def __init__(
        self,
        max_positions: int = None,
        max_risk_per_trade: float = None,
        max_daily_drawdown: float = None
    ):
        """
        Initialise le gestionnaire de positions
        
        Args:
            max_positions: Nombre max de positions simultanées
            max_risk_per_trade: Risque max par trade (% du capital)
            max_daily_drawdown: Drawdown journalier max (%)
        """
        # Configuration depuis config.py ou valeurs par défaut
        self.max_positions = max_positions or (getattr(config, 'MAX_POSITIONS', 3) if config else 3)
        self.max_risk_per_trade = max_risk_per_trade or (getattr(config, 'RISK_PER_TRADE', 0.015) if config else 0.015)
        self.max_daily_drawdown = max_daily_drawdown or (getattr(config, 'MAX_DAILY_DRAWDOWN', 0.05) if config else 0.05)
        self.max_position_heat = getattr(config, 'MAX_POSITION_HEAT', 0.08) if config else 0.08
        
        # Positions actives {coin: position_info}
        self.positions = {}
        
        # Historique des trades
        self.trade_history = deque(maxlen=1000)  # Garder 1000 derniers trades
        self.daily_trades = []
        
        # Métriques
        self.daily_pnl = 0.0
        self.daily_start_balance = 0.0
        self.current_balance = 0.0
        self.last_reset_date = datetime.now().date()
        
        # Winrate tracking
        self.recent_trades = deque(maxlen=20)  # 20 derniers trades pour winrate
        self.consecutive_losses = 0
        
        # Corrélations (pour éviter trades corrélés)
        self.coin_correlations = {}  # {coin: [correlated_coins]}
        
        logger.info(f"✅ PositionManager initialisé: max_positions={self.max_positions}, risk={self.max_risk_per_trade*100:.2f}%")
    
    def reset_daily_stats(self):
        """Réinitialise les statistiques journalières"""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_pnl = 0.0
            self.daily_trades = []
            self.last_reset_date = today
            logger.info("📊 Statistiques journalières réinitialisées")
    
    def can_open_position(self, coin: str, account_balance: float) -> Tuple[bool, str]:
        """
        Vérifie si on peut ouvrir une nouvelle position
        
        Returns:
            (can_open: bool, reason: str)
        """
        self.reset_daily_stats()
        
        # Vérifier le drawdown journalier
        if self.daily_pnl < 0:
            drawdown_percent = abs(self.daily_pnl / self.daily_start_balance) if self.daily_start_balance > 0 else 0
            if drawdown_percent >= self.max_daily_drawdown:
                return False, f"Drawdown journalier max atteint: {drawdown_percent*100:.2f}%"
        
        # Vérifier le nombre de positions
        if len(self.positions) >= self.max_positions:
            return False, f"Maximum {self.max_positions} positions atteint"
        
        # Vérifier si position déjà ouverte sur ce coin
        if coin in self.positions:
            return False, f"Position déjà ouverte sur {coin}"
        
        # Vérifier la position heat
        current_heat = len(self.positions) * self.max_risk_per_trade
        if current_heat + self.max_risk_per_trade > self.max_position_heat:
            return False, f"Heat max atteint: {current_heat*100:.2f}%"
        
        # Vérifier les corrélations
        if coin in self.coin_correlations:
            correlated = self.coin_correlations[coin]
            for pos_coin in self.positions.keys():
                if pos_coin in correlated:
                    correlation = correlated[pos_coin]
                    if correlation > 0.70:  # 70% corrélation
                        return False, f"Coin {coin} corrélé à {pos_coin} ({correlation*100:.0f}%)"
        
        return True, "OK"
    
    def calculate_position_size(
        self,
        signal_quality: float,
        account_balance: float,
        atr: float,
        entry_price: float,
        stop_loss_price: float
    ) -> float:
        """
        Calcule la taille de position avec Kelly Criterion adapté
        
        Args:
            signal_quality: Score qualité 0-100
            account_balance: Solde du compte
            atr: Average True Range
            entry_price: Prix d'entrée
            stop_loss_price: Prix du stop loss
        
        Returns:
            Taille de position en USD
        """
        # Risque de base
        base_risk = self.max_risk_per_trade
        
        # Ajuster selon la qualité du signal
        quality_multiplier = signal_quality / 100.0
        adjusted_risk = base_risk * quality_multiplier
        
        # Ajuster selon le winrate récent
        if len(self.recent_trades) >= 10:
            winrate = sum(1 for t in self.recent_trades if t.get('pnl', 0) > 0) / len(self.recent_trades)
            
            # Augmenter taille si winrate >60%
            if winrate > getattr(config, 'WINRATE_THRESHOLD_INCREASE', 0.60) if config else 0.60:
                adjusted_risk *= 1.2
            # Réduire taille si winrate <50%
            elif winrate < 0.50:
                adjusted_risk *= 0.8
        
        # Réduire taille après pertes consécutives
        consecutive_threshold = getattr(config, 'CONSECUTIVE_LOSSES_REDUCE', 3) if config else 3
        if self.consecutive_losses >= consecutive_threshold:
            reduction = 0.5 ** (self.consecutive_losses - consecutive_threshold + 1)
            adjusted_risk *= reduction
            logger.warning(f"⚠️ Réduction taille position: {consecutive_threshold}+ pertes consécutives")
        
        # Calculer la taille basée sur le risque
        risk_amount = account_balance * adjusted_risk
        price_risk = abs(entry_price - stop_loss_price)
        
        if price_risk > 0:
            position_size = risk_amount / price_risk
        else:
            position_size = account_balance * 0.01  # Fallback: 1% du capital
        
        # Limiter à 2% du capital maximum
        max_position_size = account_balance * 0.02
        position_size = min(position_size, max_position_size)
        
        # Minimum 10 USD
        position_size = max(position_size, 10.0)
        
        return round(position_size, 2)
    
    def open_position(
        self,
        coin: str,
        side: str,  # 'LONG' ou 'SHORT'
        entry_price: float,
        size: float,
        stop_loss: float,
        take_profit_1: float,
        take_profit_2: float,
        take_profit_3: float,
        signal_quality: float
    ) -> Dict:
        """
        Ouvre une nouvelle position
        
        Returns:
            Informations de la position
        """
        position = {
            'coin': coin,
            'side': side,
            'entry_price': entry_price,
            'size': size,
            'stop_loss': stop_loss,
            'stop_loss_initial': stop_loss,
            'take_profit_1': take_profit_1,
            'take_profit_2': take_profit_2,
            'take_profit_3': take_profit_3,
            'tp1_filled': False,
            'tp2_filled': False,
            'tp3_filled': False,
            'entry_time': datetime.now(),
            'signal_quality': signal_quality,
            'unrealized_pnl': 0.0,
            'trailing_activated': False,
            'break_even_activated': False,
            'max_profit': 0.0
        }
        
        self.positions[coin] = position
        logger.info(f"✅ Position ouverte: {side} {coin} @ ${entry_price:.2f} | Size: ${size:.2f} | SL: ${stop_loss:.2f}")
        
        return position
    
    def update_position(self, coin: str, current_price: float) -> Optional[Dict]:
        """
        Met à jour une position (PNL, trailing stop, etc.)
        
        Returns:
            Position mise à jour ou None si fermée
        """
        if coin not in self.positions:
            return None
        
        position = self.positions[coin]
        side = position['side']
        entry_price = position['entry_price']
        size = position['size']
        
        # Calculer PNL non réalisé
        if side == 'LONG':
            pnl_percent = ((current_price - entry_price) / entry_price) * 100
            pnl_amount = (current_price - entry_price) * size
        else:  # SHORT
            pnl_percent = ((entry_price - current_price) / entry_price) * 100
            pnl_amount = (entry_price - current_price) * size
        
        position['unrealized_pnl'] = pnl_amount
        position['pnl_percent'] = pnl_percent
        
        # Mettre à jour le profit max
        if pnl_percent > position.get('max_profit', 0):
            position['max_profit'] = pnl_percent
        
        # Trailing Stop
        self._update_trailing_stop(position, current_price, pnl_percent)
        
        # Break-even
        self._update_break_even(position, current_price, pnl_percent)
        
        # Vérifier Take Profit
        self._check_take_profits(position, current_price)
        
        return position
    
    def _update_trailing_stop(self, position: Dict, current_price: float, pnl_percent: float):
        """Met à jour le trailing stop"""
        trailing_activation = getattr(config, 'TRAILING_ACTIVATION', 0.5) if config else 0.5
        trailing_percent = getattr(config, 'TRAILING_PERCENT', 50) if config else 50
        
        if pnl_percent >= trailing_activation and not position.get('trailing_activated', False):
            position['trailing_activated'] = True
            logger.info(f"🔄 Trailing stop activé pour {position['coin']}")
        
        if position.get('trailing_activated', False):
            side = position['side']
            max_profit = position.get('max_profit', 0)
            
            # Calculer le nouveau SL basé sur le profit max
            if max_profit > trailing_activation:
                # Trail à X% du gain max
                trail_distance = max_profit * (trailing_percent / 100.0)
                new_sl_percent = max_profit - trail_distance
                
                if side == 'LONG':
                    new_sl_price = position['entry_price'] * (1 + new_sl_percent / 100)
                    if new_sl_price > position['stop_loss']:
                        position['stop_loss'] = new_sl_price
                        logger.debug(f"📈 Trailing SL mis à jour: {position['coin']} @ ${new_sl_price:.2f}")
                else:  # SHORT
                    new_sl_price = position['entry_price'] * (1 - new_sl_percent / 100)
                    if new_sl_price < position['stop_loss']:
                        position['stop_loss'] = new_sl_price
                        logger.debug(f"📉 Trailing SL mis à jour: {position['coin']} @ ${new_sl_price:.2f}")
    
    def _update_break_even(self, position: Dict, current_price: float, pnl_percent: float):
        """Déplace le SL à break-even"""
        break_even_activation = getattr(config, 'BREAK_EVEN_ACTIVATION', 0.8) if config else 0.8
        
        if pnl_percent >= break_even_activation and not position.get('break_even_activated', False):
            # Déplacer SL à entry + fees
            try:
                import config
                fees = getattr(config, 'get_hyperliquid_fees_by_volume', lambda: {'maker_percent': 0.01})()
                fees_percent = fees.get('maker_percent', 0.01) / 100
            except:
                fees_percent = 0.0001  # 0.01% par défaut
            
            side = position['side']
            entry = position['entry_price']
            
            if side == 'LONG':
                new_sl = entry * (1 + fees_percent * 2)  # Entrée + sortie
            else:
                new_sl = entry * (1 - fees_percent * 2)
            
            # Ne déplacer que si meilleur que le SL actuel
            if (side == 'LONG' and new_sl > position['stop_loss']) or \
               (side == 'SHORT' and new_sl < position['stop_loss']):
                position['stop_loss'] = new_sl
                position['break_even_activated'] = True
                logger.info(f"✅ Break-even activé: {position['coin']} @ ${new_sl:.2f}")
    
    def _check_take_profits(self, position: Dict, current_price: float):
        """Vérifie si les take profits sont atteints"""
        side = position['side']
        
        # TP1
        if not position.get('tp1_filled', False):
            if (side == 'LONG' and current_price >= position['take_profit_1']) or \
               (side == 'SHORT' and current_price <= position['take_profit_1']):
                position['tp1_filled'] = True
                logger.info(f"🎯 TP1 atteint: {position['coin']} @ ${current_price:.2f}")
        
        # TP2
        if position.get('tp1_filled', False) and not position.get('tp2_filled', False):
            if (side == 'LONG' and current_price >= position['take_profit_2']) or \
               (side == 'SHORT' and current_price <= position['take_profit_2']):
                position['tp2_filled'] = True
                logger.info(f"🎯 TP2 atteint: {position['coin']} @ ${current_price:.2f}")
        
        # TP3
        if position.get('tp2_filled', False) and not position.get('tp3_filled', False):
            if (side == 'LONG' and current_price >= position['take_profit_3']) or \
               (side == 'SHORT' and current_price <= position['take_profit_3']):
                position['tp3_filled'] = True
                logger.info(f"🎯 TP3 atteint: {position['coin']} @ ${current_price:.2f}")
    
    def check_stop_loss(self, coin: str, current_price: float) -> bool:
        """
        Vérifie si le stop loss est atteint
        
        Returns:
            True si SL atteint, False sinon
        """
        if coin not in self.positions:
            return False
        
        position = self.positions[coin]
        side = position['side']
        stop_loss = position['stop_loss']
        
        if (side == 'LONG' and current_price <= stop_loss) or \
           (side == 'SHORT' and current_price >= stop_loss):
            return True
        
        return False
    
    def check_time_stop(self, coin: str) -> bool:
        """
        Vérifie si le stop loss temporel est atteint
        
        Returns:
            True si temps écoulé sans profit, False sinon
        """
        if coin not in self.positions:
            return False
        
        position = self.positions[coin]
        entry_time = position['entry_time']
        sl_time_minutes = getattr(config, 'SL_TIME_MINUTES', 10) if config else 10
        
        time_elapsed = (datetime.now() - entry_time).total_seconds() / 60
        
        # Si temps écoulé ET aucun profit
        if time_elapsed >= sl_time_minutes and position.get('unrealized_pnl', 0) <= 0:
            return True
        
        return False
    
    def close_position(self, coin: str, exit_price: float, reason: str = "Manual") -> Dict:
        """
        Ferme une position
        
        Returns:
            Informations du trade fermé
        """
        if coin not in self.positions:
            return None
        
        position = self.positions[coin]
        side = position['side']
        entry_price = position['entry_price']
        size = position['size']
        
        # Calculer PNL final
        if side == 'LONG':
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100
            pnl_amount = (exit_price - entry_price) * size
        else:  # SHORT
            pnl_percent = ((entry_price - exit_price) / entry_price) * 100
            pnl_amount = (entry_price - exit_price) * size
        
        # Soustraire les frais
        try:
            import config
            fees = getattr(config, 'get_hyperliquid_fees_by_volume', lambda: {'maker_percent': 0.01})()
            fees_percent = fees.get('maker_percent', 0.01) / 100
        except:
            fees_percent = 0.0001
        
        fees_amount = (entry_price + exit_price) * size * fees_percent
        net_pnl = pnl_amount - fees_amount
        net_pnl_percent = (net_pnl / (entry_price * size)) * 100
        
        # Créer le trade record
        trade_record = {
            'coin': coin,
            'side': side,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'size': size,
            'pnl': net_pnl,
            'pnl_percent': net_pnl_percent,
            'entry_time': position['entry_time'],
            'exit_time': datetime.now(),
            'duration_minutes': (datetime.now() - position['entry_time']).total_seconds() / 60,
            'reason': reason,
            'signal_quality': position.get('signal_quality', 0),
            'max_profit': position.get('max_profit', 0)
        }
        
        # Mettre à jour les statistiques
        self.trade_history.append(trade_record)
        self.daily_trades.append(trade_record)
        self.recent_trades.append(trade_record)
        self.daily_pnl += net_pnl
        
        # Mettre à jour les pertes consécutives
        if net_pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        # Supprimer la position
        del self.positions[coin]
        
        logger.info(f"🔒 Position fermée: {coin} | PNL: ${net_pnl:.2f} ({net_pnl_percent:+.2f}%) | Raison: {reason}")
        
        return trade_record
    
    def get_statistics(self) -> Dict:
        """Retourne les statistiques de trading"""
        if not self.trade_history:
            return {
                'total_trades': 0,
                'winrate': 0,
                'profit_factor': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'total_pnl': 0,
                'daily_pnl': self.daily_pnl
            }
        
        trades = list(self.trade_history)
        total_trades = len(trades)
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] < 0]
        
        winrate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        total_wins = sum(t['pnl'] for t in winning_trades)
        total_losses = abs(sum(t['pnl'] for t in losing_trades))
        
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        avg_win = total_wins / len(winning_trades) if winning_trades else 0
        avg_loss = total_losses / len(losing_trades) if losing_trades else 0
        
        total_pnl = sum(t['pnl'] for t in trades)
        
        return {
            'total_trades': total_trades,
            'winrate': winrate,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'total_pnl': total_pnl,
            'daily_pnl': self.daily_pnl,
            'active_positions': len(self.positions),
            'consecutive_losses': self.consecutive_losses
        }
    
    def should_stop_trading(self) -> Tuple[bool, str]:
        """
        Vérifie si le trading doit être arrêté
        
        Returns:
            (should_stop: bool, reason: str)
        """
        self.reset_daily_stats()
        
        # Vérifier le drawdown journalier
        if self.daily_start_balance > 0:
            drawdown_percent = abs(self.daily_pnl / self.daily_start_balance)
            if drawdown_percent >= self.max_daily_drawdown:
                return True, f"Drawdown journalier max atteint: {drawdown_percent*100:.2f}%"
        
        return False, "OK"
    
    def set_daily_start_balance(self, balance: float):
        """Définit le solde de départ de la journée"""
        self.daily_start_balance = balance
        logger.info(f"💰 Solde de départ: ${balance:,.2f}")

