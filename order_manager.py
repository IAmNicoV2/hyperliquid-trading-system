"""
Gestionnaire d'ordres de trading
Gère la liste des ordres proposés et exécutés
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum
import json
import os

logger = logging.getLogger(__name__)

class OrderStatus(Enum):
    PENDING = "PENDING"  # Ordre proposé, en attente de validation
    ACCEPTED = "ACCEPTED"  # Ordre accepté, prêt à être exécuté
    EXECUTED = "EXECUTED"  # Ordre exécuté
    REJECTED = "REJECTED"  # Ordre rejeté
    CANCELLED = "CANCELLED"  # Ordre annulé
    CLOSED = "CLOSED"  # Position fermée

class OrderManager:
    """
    Gère les ordres de trading
    """
    
    def __init__(self, orders_file: str = "orders_history.json"):
        self.orders_file = orders_file
        self.pending_orders: List[Dict] = []  # Ordres en attente
        self.accepted_orders: List[Dict] = []  # Ordres acceptés
        self.executed_orders: List[Dict] = []  # Ordres exécutés
        self.closed_positions: List[Dict] = []  # Positions fermées
        self.load_orders()
    
    def add_order(self, order_details: Dict) -> str:
        """
        Ajoute un ordre à la liste des ordres en attente
        
        Returns:
            order_id: Identifiant unique de l'ordre
        """
        order_id = f"{order_details['coin']}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        order = {
            'order_id': order_id,
            'status': OrderStatus.PENDING.value,
            'coin': order_details['coin'],
            'signal': order_details['signal'],
            'entry_price': order_details['entry_price'],
            'stop_loss': order_details['stop_loss'],
            'take_profit': order_details['take_profit'],
            'stop_loss_percent': order_details['stop_loss_percent'],
            'take_profit_percent': order_details['take_profit_percent'],
            'risk_reward_ratio': order_details['risk_reward_ratio'],
            'confidence_score': order_details['confidence_score'],
            'signal_quality': order_details['signal_quality'],
            'buy_signals': order_details.get('buy_signals', 0),
            'sell_signals': order_details.get('sell_signals', 0),
            'reasons': order_details.get('reasons', []),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'executed_at': None,
            'exit_price': None,
            'exit_reason': None,
            'pnl': None,
            'pnl_percent': None
        }
        
        self.pending_orders.append(order)
        self.save_orders()
        
        logger.info(f"📝 Ordre ajouté: {order_id} - {order['coin']} {order['signal']} @ ${order['entry_price']:.2f}")
        
        return order_id
    
    def accept_order(self, order_id: str) -> bool:
        """Accepte un ordre"""
        order = self._find_order(order_id, self.pending_orders)
        if order:
            order['status'] = OrderStatus.ACCEPTED.value
            order['updated_at'] = datetime.now().isoformat()
            self.accepted_orders.append(order)
            self.pending_orders.remove(order)
            self.save_orders()
            logger.info(f"✅ Ordre accepté: {order_id}")
            return True
        return False
    
    def reject_order(self, order_id: str, reason: str = "") -> bool:
        """Rejette un ordre"""
        order = self._find_order(order_id, self.pending_orders)
        if order:
            order['status'] = OrderStatus.REJECTED.value
            order['updated_at'] = datetime.now().isoformat()
            order['rejection_reason'] = reason
            self.pending_orders.remove(order)
            self.save_orders()
            logger.info(f"❌ Ordre rejeté: {order_id} - {reason}")
            return True
        return False
    
    def execute_order(self, order_id: str) -> bool:
        """Marque un ordre comme exécuté"""
        order = self._find_order(order_id, self.accepted_orders)
        if order:
            order['status'] = OrderStatus.EXECUTED.value
            order['executed_at'] = datetime.now().isoformat()
            order['updated_at'] = datetime.now().isoformat()
            self.executed_orders.append(order)
            self.accepted_orders.remove(order)
            self.save_orders()
            logger.info(f"🚀 Ordre exécuté: {order_id}")
            return True
        return False
    
    def close_position(self, order_id: str, exit_price: float, exit_reason: str) -> bool:
        """Ferme une position"""
        order = self._find_order(order_id, self.executed_orders)
        if order:
            order['status'] = OrderStatus.CLOSED.value
            order['exit_price'] = exit_price
            order['exit_reason'] = exit_reason
            order['updated_at'] = datetime.now().isoformat()
            
            # Calculer P&L
            if order['signal'] == 'ACHAT':
                pnl_percent = ((exit_price - order['entry_price']) / order['entry_price']) * 100
            else:  # VENTE
                pnl_percent = ((order['entry_price'] - exit_price) / order['entry_price']) * 100
            
            order['pnl_percent'] = round(pnl_percent, 2)
            order['pnl'] = round(pnl_percent * order['entry_price'] / 100, 2)  # Approximation
            
            self.closed_positions.append(order)
            self.executed_orders.remove(order)
            self.save_orders()
            
            logger.info(f"🔒 Position fermée: {order_id} - P&L: {order['pnl_percent']:.2f}%")
            return True
        return False
    
    def get_all_orders(self) -> Dict:
        """Retourne tous les ordres"""
        return {
            'pending': self.pending_orders,
            'accepted': self.accepted_orders,
            'executed': self.executed_orders,
            'closed': self.closed_positions
        }
    
    def get_pending_orders(self) -> List[Dict]:
        """Retourne les ordres en attente"""
        return self.pending_orders
    
    def get_statistics(self) -> Dict:
        """Calcule les statistiques de performance"""
        if not self.closed_positions:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'winrate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'total_pnl': 0.0
            }
        
        winning_trades = [t for t in self.closed_positions if t.get('pnl_percent', 0) > 0]
        losing_trades = [t for t in self.closed_positions if t.get('pnl_percent', 0) <= 0]
        
        total_trades = len(self.closed_positions)
        wins = len(winning_trades)
        losses = len(losing_trades)
        
        winrate = (wins / total_trades * 100) if total_trades > 0 else 0.0
        
        avg_win = sum(t.get('pnl_percent', 0) for t in winning_trades) / wins if wins > 0 else 0.0
        avg_loss = sum(t.get('pnl_percent', 0) for t in losing_trades) / losses if losses > 0 else 0.0
        
        gross_profit = sum(t.get('pnl_percent', 0) for t in winning_trades)
        gross_loss = abs(sum(t.get('pnl_percent', 0) for t in losing_trades))
        
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0
        
        total_pnl = sum(t.get('pnl_percent', 0) for t in self.closed_positions)
        
        return {
            'total_trades': total_trades,
            'winning_trades': wins,
            'losing_trades': losses,
            'winrate': round(winrate, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'total_pnl': round(total_pnl, 2)
        }
    
    def _find_order(self, order_id: str, orders_list: List[Dict]) -> Optional[Dict]:
        """Trouve un ordre par son ID"""
        for order in orders_list:
            if order['order_id'] == order_id:
                return order
        return None
    
    def save_orders(self):
        """Sauvegarde les ordres dans un fichier JSON"""
        try:
            data = {
                'pending': self.pending_orders,
                'accepted': self.accepted_orders,
                'executed': self.executed_orders,
                'closed': self.closed_positions
            }
            with open(self.orders_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erreur sauvegarde ordres: {e}")
    
    def load_orders(self):
        """Charge les ordres depuis un fichier JSON"""
        if os.path.exists(self.orders_file):
            try:
                with open(self.orders_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.pending_orders = data.get('pending', [])
                    self.accepted_orders = data.get('accepted', [])
                    self.executed_orders = data.get('executed', [])
                    self.closed_positions = data.get('closed', [])
                logger.info(f"📂 {len(self.pending_orders)} ordres en attente chargés")
            except Exception as e:
                logger.error(f"Erreur chargement ordres: {e}")

