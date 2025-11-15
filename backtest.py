"""
Backtesting Engine pour Scalping - Simulation complète avec métriques
"""

import pandas as pd
import numpy as np
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import StringIO

logger = logging.getLogger(__name__)

try:
    import config
    from hyperliquid_signals import HyperliquidSignalGenerator
    from position_manager import PositionManager
except ImportError as e:
    logger.error(f"Erreur d'import: {e}")
    config = None


class ScalpingBacktest:
    """Moteur de backtesting pour stratégie de scalping"""
    
    def __init__(
        self,
        initial_capital: float = None,
        commission_taker: float = None,
        commission_maker: float = None,
        slippage: float = None,
        latency_ms: int = None
    ):
        """
        Initialise le backtest
        
        Args:
            initial_capital: Capital initial
            commission_taker: Frais taker (%)
            commission_maker: Frais maker (%)
            slippage: Slippage par trade (%)
            latency_ms: Latence simulée (ms)
        """
        # Configuration depuis config.py ou valeurs par défaut
        self.initial_capital = initial_capital or (getattr(config, 'BACKTEST_INITIAL_CAPITAL', 10000) if config else 10000)
        self.commission_taker = commission_taker or (getattr(config, 'BACKTEST_COMMISSION_TAKER', 0.00035) if config else 0.00035)
        self.commission_maker = commission_maker or (getattr(config, 'BACKTEST_COMMISSION_MAKER', 0.0001) if config else 0.0001)
        self.slippage = slippage or (getattr(config, 'BACKTEST_SLIPPAGE', 0.0002) if config else 0.0002)
        self.latency_ms = latency_ms or (getattr(config, 'BACKTEST_LATENCY_MS', 100) if config else 100)
        
        # État du backtest
        self.capital = self.initial_capital
        self.equity = self.initial_capital
        self.equity_curve = []
        self.closed_trades = []
        self.positions = {}  # {coin: position_dict}
        
        # Position manager (pour vérifications uniquement)
        self.position_manager = PositionManager()
        self.position_manager.set_daily_start_balance(self.initial_capital)
        
        # Signal generator
        self.signal_generator = None
        
        # Métriques
        self.max_drawdown = 0.0
        self.max_equity = self.initial_capital
        
        logger.info(f"✅ Backtest initialisé: Capital=${self.initial_capital:,.2f}, Slippage={self.slippage*100:.3f}%")
    
    def load_historical_data(self, coin: str, interval: str = "5m", days: int = 30) -> List[Dict]:
        """
        Charge les données historiques depuis Hyperliquid (chargement par lots si nécessaire)
        
        Args:
            coin: Symbole de la crypto
            interval: Intervalle (1m, 5m, etc.)
            days: Nombre de jours de données
        
        Returns:
            Liste de chandeliers
        """
        try:
            generator = HyperliquidSignalGenerator(coin=coin, interval=interval)
            
            # Calculer le nombre de chandeliers nécessaires
            intervals_per_day = {
                '1m': 1440,
                '5m': 288,
                '15m': 96,
                '1h': 24,
                '4h': 6,
                '1d': 1
            }
            candles_needed = intervals_per_day.get(interval, 288) * days
            
            logger.info(f"📥 Chargement de {candles_needed} chandeliers pour {coin} ({interval})...")
            
            # Charger par lots de 2000 (limite API)
            all_candles = []
            max_per_request = 2000
            
            if candles_needed <= max_per_request:
                candles = generator.fetch_historical_candles(limit=candles_needed)
                all_candles.extend(candles if candles else [])
            else:
                # Charger plusieurs lots
                num_requests = (candles_needed // max_per_request) + 1
                logger.info(f"   Chargement en {num_requests} lots...")
                
                for i in range(num_requests):
                    limit = min(max_per_request, candles_needed - len(all_candles))
                    if limit <= 0:
                        break
                    candles = generator.fetch_historical_candles(limit=limit)
                    if candles:
                        all_candles.extend(candles)
                        logger.info(f"   Lot {i+1}/{num_requests}: {len(candles)} chandeliers chargés")
                    else:
                        break
            
            candles = all_candles
            
            if not candles:
                logger.error(f"❌ Impossible de charger les données pour {coin}")
                return []
            
            logger.info(f"✅ {len(candles)} chandeliers chargés")
            return candles
            
        except Exception as e:
            logger.error(f"Erreur chargement données: {e}", exc_info=True)
            return []
    
    def calculate_position_size(self, signal_quality: float, account_balance: float, atr: float, price: float) -> Dict:
        """
        Calcule la taille de position avec risque limité à 1%
        
        Returns:
            {'size_usd': float, 'risk_usd': float, 'sl_distance_percent': float}
        """
        # LIMITE : 1% risque par trade
        max_risk_usd = account_balance * 0.01
        
        # Quality 70-100 → multiplier 0.5x-1x
        quality_multiplier = max(0.5, min(1.0, (signal_quality - 70) / 30)) if signal_quality >= 70 else 0.3
        position_risk = max_risk_usd * quality_multiplier
        
        # SL distance basé ATR (0.5%-1.2%)
        if atr > 0 and price > 0:
            atr_percent = atr / price
            sl_distance_percent = max(0.005, min(0.012, atr_percent * 1.2))
        else:
            sl_distance_percent = 0.008  # 0.8% par défaut
        
        # Size = risk / SL%
        position_size_usd = position_risk / sl_distance_percent
        
        # PLAFOND : 5% capital max
        position_size_usd = min(position_size_usd, account_balance * 0.05)
        position_size_usd = max(10.0, position_size_usd)
        
        return {
            'size_usd': round(position_size_usd, 2),
            'risk_usd': round(position_risk, 2),
            'sl_distance_percent': round(sl_distance_percent * 100, 2)
        }
    
    def calculate_sl_tp_levels(self, entry_price: float, signal_type: str, atr: float) -> Dict:
        """
        Calcule SL/TP réalistes basés sur ATR avec ratio 1.5:1
        """
        if atr > 0 and entry_price > 0:
            atr_percent = atr / entry_price
        else:
            atr_percent = 0.008  # 0.8% par défaut
        
        # SL : 0.6%-1% (scalping) - utiliser ATR si disponible
        if atr_percent > 0:
            sl_distance = max(0.006, min(0.01, atr_percent * 1.2))
        else:
            sl_distance = 0.008  # 0.8% par défaut
        
        if signal_type == 'ACHAT' or signal_type == 'BUY':
            sl_price = entry_price * (1 - sl_distance)
            # TP : ratio 1.5:1 minimum, mais ajuster selon ATR
            tp_distance = max(sl_distance * 1.5, 0.012)  # Minimum 1.2%
            tp_price = entry_price * (1 + tp_distance)
        else:  # VENTE / SELL
            sl_price = entry_price * (1 + sl_distance)
            tp_distance = max(sl_distance * 1.5, 0.012)  # Minimum 1.2%
            tp_price = entry_price * (1 - tp_distance)
        
        return {
            'stop_loss': round(sl_price, 2),
            'take_profit': round(tp_price, 2),
            'sl_percent': round(sl_distance * 100, 2),
            'tp_percent': round(tp_distance * 100, 2),
            'risk_reward': round(tp_distance / sl_distance, 2)
        }
    
    def execute_trade(self, timestamp: float, coin: str, signal: str, price: float, size_info: Dict, sl_tp: Dict) -> Optional[Dict]:
        """
        Ouvre une position avec fees et slippage
        """
        position_size_usd = size_info['size_usd']
        
        # Vérifier capital disponible (garder 5% marge)
        if position_size_usd > self.capital * 0.95:
            return None
        
        # FEES taker (0.035%)
        entry_fee_percent = self.commission_taker
        entry_fee = position_size_usd * entry_fee_percent
        
        # Slippage (0.02%)
        slippage_percent = self.slippage
        slippage = position_size_usd * slippage_percent
        
        # Prix ajusté
        if signal == 'ACHAT' or signal == 'BUY':
            actual_entry_price = price * (1 + slippage_percent)
        else:
            actual_entry_price = price * (1 - slippage_percent)
        
        position = {
            'coin': coin,
            'type': signal,
            'entry_price': actual_entry_price,
            'entry_time': timestamp,
            'size_usd': position_size_usd,
            'entry_fee': entry_fee,
            'slippage': slippage,
            'stop_loss': sl_tp['stop_loss'],
            'take_profit': sl_tp['take_profit'],
            'sl_percent': sl_tp['sl_percent'],
            'tp_percent': sl_tp['tp_percent'],
            'initial_stop_loss': sl_tp['stop_loss']  # Garder SL initial pour trailing
        }
        
        # Déduire capital
        self.capital -= (position_size_usd + entry_fee + slippage)
        self.positions[coin] = position
        
        return position
    
    def check_exit_conditions(self, timestamp: float, coin: str, current_price: float) -> Optional[Dict]:
        """
        Vérifie les conditions de sortie avec trailing stop et break-even
        """
        if coin not in self.positions:
            return None
        
        position = self.positions[coin]
        entry_price = position['entry_price']
        position_type = position['type']
        
        if position_type == 'ACHAT' or position_type == 'BUY':
            pnl_percent = (current_price - entry_price) / entry_price
            
            # Stop Loss
            if current_price <= position['stop_loss']:
                return self.close_position(timestamp, coin, current_price, 'STOP_LOSS')
            
            # Take Profit
            if current_price >= position['take_profit']:
                return self.close_position(timestamp, coin, current_price, 'TAKE_PROFIT')
            
            # Trailing stop : trail dès +0.8%
            if pnl_percent > 0.008:
                new_sl = entry_price * (1 + pnl_percent * 0.5)
                position['stop_loss'] = max(position['stop_loss'], new_sl)
            
            # Break-even : SL à entry+fees dès +0.5%
            if pnl_percent > 0.005:
                breakeven_price = entry_price * 1.001
                position['stop_loss'] = max(position['stop_loss'], breakeven_price)
        
        else:  # VENTE / SELL
            pnl_percent = (entry_price - current_price) / entry_price
            
            if current_price >= position['stop_loss']:
                return self.close_position(timestamp, coin, current_price, 'STOP_LOSS')
            
            if current_price <= position['take_profit']:
                return self.close_position(timestamp, coin, current_price, 'TAKE_PROFIT')
            
            if pnl_percent > 0.008:
                new_sl = entry_price * (1 - pnl_percent * 0.5)
                position['stop_loss'] = min(position['stop_loss'], new_sl)
            
            if pnl_percent > 0.005:
                breakeven_price = entry_price * 0.999
                position['stop_loss'] = min(position['stop_loss'], breakeven_price)
        
        # Time stop : fermer après 15 min si profit <0.2%
        # Gérer les timestamps (int ou datetime)
        try:
            if isinstance(position['entry_time'], (int, float)) and isinstance(timestamp, (int, float)):
                time_elapsed = (timestamp - position['entry_time']) / 60  # minutes
            else:
                # Convertir en datetime si nécessaire
                from datetime import datetime
                if isinstance(position['entry_time'], (int, float)):
                    entry_dt = datetime.fromtimestamp(position['entry_time'])
                else:
                    entry_dt = position['entry_time']
                if isinstance(timestamp, (int, float)):
                    exit_dt = datetime.fromtimestamp(timestamp)
                else:
                    exit_dt = timestamp
                time_elapsed = (exit_dt - entry_dt).total_seconds() / 60
        except:
            time_elapsed = 0
        
        if time_elapsed > 15 and pnl_percent < 0.002:
            return self.close_position(timestamp, coin, current_price, 'TIME_STOP')
        
        return None
    
    def close_position(self, timestamp: float, coin: str, exit_price: float, reason: str) -> Dict:
        """
        Ferme une position et calcule P&L net
        """
        position = self.positions[coin]
        
        # Exit fees + slippage
        exit_fee_percent = self.commission_taker
        exit_slippage_percent = self.slippage
        
        size_usd = position['size_usd']
        entry_price = position['entry_price']
        
        # Prix sortie ajusté
        if position['type'] == 'ACHAT' or position['type'] == 'BUY':
            actual_exit_price = exit_price * (1 - exit_slippage_percent)
        else:
            actual_exit_price = exit_price * (1 + exit_slippage_percent)
        
        # P&L brut
        if position['type'] == 'ACHAT' or position['type'] == 'BUY':
            pnl_gross = size_usd * ((actual_exit_price - entry_price) / entry_price)
        else:
            pnl_gross = size_usd * ((entry_price - actual_exit_price) / entry_price)
        
        # Fees totaux
        exit_fee = size_usd * exit_fee_percent
        total_fees = position['entry_fee'] + exit_fee
        total_slippage = position['slippage'] + (size_usd * exit_slippage_percent)
        
        # P&L NET
        pnl_net = pnl_gross - total_fees - total_slippage
        
        # Retour capital + P&L
        self.capital += (size_usd + pnl_net)
        self.equity = self.capital + sum(p['size_usd'] for p in self.positions.values() if p != position)
        
        # Trade record
        trade = {
            'entry_time': position['entry_time'],
            'exit_time': timestamp,
            'coin': coin,
            'type': position['type'],
            'entry_price': entry_price,
            'exit_price': actual_exit_price,
            'size_usd': size_usd,
            'pnl_gross': round(pnl_gross, 2),
            'pnl_net': round(pnl_net, 2),
            'pnl_percent': round((pnl_net / size_usd) * 100, 2),
            'fees': round(total_fees, 2),
            'slippage': round(total_slippage, 2),
            'exit_reason': reason,
            'duration_min': round((timestamp - position['entry_time']) / 60, 1)
        }
        
        self.closed_trades.append(trade)
        
        # Update drawdown
        if self.equity > self.max_equity:
            self.max_equity = self.equity
        
        current_drawdown = (self.max_equity - self.equity) / self.max_equity if self.max_equity > 0 else 0
        self.max_drawdown = max(self.max_drawdown, current_drawdown)
        
        del self.positions[coin]
        return trade
    
    def run(
        self,
        coin: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        signal_quality_threshold: float = None
    ) -> Dict:
        """
        Exécute le backtest
        
        Args:
            coin: Coin à backtester
            start_date: Date de début (optionnel)
            end_date: Date de fin (optionnel)
            signal_quality_threshold: Seuil qualité signal (0-100)
        
        Returns:
            Résultats du backtest
        """
        logger.info(f"🚀 Démarrage du backtest pour {coin}")
        
        # Charger les données historiques (30 jours minimum)
        try:
            import config
            interval = getattr(config, 'DEFAULT_INTERVAL', '5m')
            days = 30  # 30 jours pour statistiques significatives
        except:
            interval = '5m'
            days = 30
        
        candles = self.load_historical_data(coin, interval=interval, days=days)
        if not candles:
            return {'error': 'Impossible de charger les données'}
        
        # Filtrer par dates si fournies
        if start_date or end_date:
            filtered_candles = []
            for candle in candles:
                candle_time = datetime.fromtimestamp(candle['time'])
                if start_date and candle_time < start_date:
                    continue
                if end_date and candle_time > end_date:
                    continue
                filtered_candles.append(candle)
            candles = filtered_candles
        
        if len(candles) < 100:
            return {'error': f'Pas assez de données: {len(candles)} chandeliers'}
        
        # Initialiser le générateur de signaux
        try:
            import config
            interval = getattr(config, 'DEFAULT_INTERVAL', '5m')
            signal_threshold = signal_quality_threshold or getattr(config, 'SIGNAL_QUALITY_THRESHOLD', 82)
        except:
            interval = '5m'
            signal_threshold = signal_quality_threshold or 82
        
        self.signal_generator = HyperliquidSignalGenerator(coin=coin, interval=interval)
        self.signal_generator.candles = candles
        
        # Statistiques pour debug
        stats = {
            'total_signals': 0,
            'neutral_signals': 0,
            'quality_too_low': 0,
            'filters_failed': 0,
            'positions_opened': 0
        }
        
        # Commencer après suffisamment de bougies pour avoir des indicateurs stables
        # Pour timeframe 5m, on a besoin de ~50 bougies (EMA50 nécessite 50)
        start_index = max(50, int(len(candles) * 0.05))  # Au moins 5% des données pour warm-up
        
        logger.info(f"📊 Simulation de {len(candles)} chandeliers (démarrage à l'index {start_index})...")
        
        for i in range(start_index, len(candles)):
            try:
                # Mettre à jour les chandeliers
                self.signal_generator.candles = candles[:i+1]
                self.signal_generator.current_price = candles[i]['close']
                
                # Analyser
                analysis = self.signal_generator.analyze()
                
                if 'error' in analysis:
                    continue
                
                signal = analysis.get('signal')
                stats['total_signals'] += 1
                
                if signal == 'NEUTRE':
                    stats['neutral_signals'] += 1
                    continue
                
                # Vérifier la qualité du signal
                signal_quality = self._calculate_signal_quality(analysis)
                if signal_quality < signal_threshold:
                    stats['quality_too_low'] += 1
                    if i % 200 == 0:  # Log occasionnel
                        logger.debug(f"Signal qualité insuffisant: {signal_quality:.1f} < {signal_threshold}")
                    continue
                
                # Vérifier les filtres d'entrée (stricts)
                should_enter, reason = self._should_enter_trade(analysis)
                if not should_enter:
                    stats['filters_failed'] += 1
                    continue
                
                logger.info(f"✅ Signal {signal} détecté à l'index {i} | Qualité: {signal_quality:.1f}/100")
                stats['positions_opened'] += 1
                
                # Vérifier si on peut ouvrir une position
                can_open, reason = self.position_manager.can_open_position(coin, self.capital)
                if not can_open:
                    # Si position déjà ouverte, on skip (on ne trade qu'une position à la fois par coin)
                    if coin in self.position_manager.positions:
                        continue
                    # Sinon, on continue même si limite atteinte (pour backtest)
                    pass
                
                # Calculer SL/TP réalistes
                entry_price = candles[i]['close']
                atr = analysis.get('indicators', {}).get('atr', 0)
                
                sl_tp = self.calculate_sl_tp_levels(entry_price, signal, atr)
                
                # Calculer la taille de position
                size_info = self.calculate_position_size(signal_quality, self.equity, atr, entry_price)
                
                # Vérifier capital disponible
                if size_info['size_usd'] > self.equity * 0.95:
                    continue
                
                # Ouvrir la position
                timestamp = candles[i]['time']
                position = self.execute_trade(timestamp, coin, signal, entry_price, size_info, sl_tp)
                
                if not position:
                    continue
                
                # Chercher la sortie dans les bougies suivantes
                max_lookahead = min(100, len(candles) - i - 1)  # Max 100 bougies (100 minutes)
                trade_closed = None
                
                for j in range(i + 1, i + 1 + max_lookahead):
                    current_candle = candles[j]
                    current_price = current_candle['close']
                    current_timestamp = current_candle['time']
                    
                    # Vérifier conditions de sortie
                    trade_closed = self.check_exit_conditions(current_timestamp, coin, current_price)
                    if trade_closed:
                        break
                
                # Si pas de sortie trouvée, fermer à la fin du lookahead
                if not trade_closed:
                    if i + max_lookahead < len(candles):
                        exit_price = candles[i + max_lookahead]['close']
                        exit_timestamp = candles[i + max_lookahead]['time']
                    else:
                        exit_price = candles[-1]['close']
                        exit_timestamp = candles[-1]['time']
                    trade_closed = self.close_position(exit_timestamp, coin, exit_price, 'TIMEOUT')
                
                if trade_closed:
                    # Mettre à jour equity curve
                    self.equity_curve.append({
                        'time': trade_closed['exit_time'],
                        'equity': self.equity,
                        'pnl': trade_closed['pnl_net']
                    })
                
            except Exception as e:
                logger.error(f"Erreur lors du backtest à l'index {i}: {e}", exc_info=True)
                continue
        
        # Afficher les statistiques de debug
        logger.info(f"📊 Statistiques backtest:")
        logger.info(f"   Total signaux analysés: {stats['total_signals']}")
        logger.info(f"   Signaux NEUTRE: {stats['neutral_signals']}")
        logger.info(f"   Qualité insuffisante: {stats['quality_too_low']}")
        logger.info(f"   Filtres non passés: {stats['filters_failed']}")
        logger.info(f"   Positions ouvertes: {stats['positions_opened']}")
        
        # Calculer les métriques finales
        metrics = self._calculate_metrics()
        metrics['debug_stats'] = stats
        
        # Afficher métriques détaillées
        self.print_detailed_metrics()
        
        # Analyser les trades perdants
        if self.closed_trades:
            self.analyze_losing_trades()
        
        return metrics
    
    def analyze_losing_trades(self):
        """
        Identifier pourquoi trades perdent
        """
        losing_trades = [t for t in self.closed_trades if t['pnl_net'] < 0]
        
        if not losing_trades:
            print("\n✅ Aucun trade perdant à analyser")
            return
        
        print("\n" + "="*60)
        print("🔍 ANALYSE DES TRADES PERDANTS")
        print("="*60)
        
        # Par raison de sortie
        exit_reasons = {}
        for trade in losing_trades:
            reason = trade['exit_reason']
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        
        print("\nRaisons de sortie :")
        for reason, count in sorted(exit_reasons.items(), key=lambda x: -x[1]):
            pct = count / len(losing_trades) * 100
            print(f"  {reason}: {count} ({pct:.1f}%)")
        
        # Durée moyenne des pertes
        avg_duration_loss = sum(t['duration_min'] for t in losing_trades) / len(losing_trades)
        print(f"\nDurée moyenne pertes : {avg_duration_loss:.1f} min")
        
        # Type de signal
        buy_losses = sum(1 for t in losing_trades if t['type'] in ['ACHAT', 'BUY'])
        sell_losses = len(losing_trades) - buy_losses
        print(f"\nBUY perdants : {buy_losses}")
        print(f"SELL perdants : {sell_losses}")
        
        # Perte moyenne
        avg_loss = sum(t['pnl_net'] for t in losing_trades) / len(losing_trades)
        print(f"\nPerte moyenne : ${avg_loss:.2f}")
        
        # Analyse par durée
        short_losses = [t for t in losing_trades if t['duration_min'] < 5]
        medium_losses = [t for t in losing_trades if 5 <= t['duration_min'] < 15]
        long_losses = [t for t in losing_trades if t['duration_min'] >= 15]
        
        print(f"\nPertes par durée :")
        print(f"  <5 min: {len(short_losses)} ({len(short_losses)/len(losing_trades)*100:.1f}%)")
        print(f"  5-15 min: {len(medium_losses)} ({len(medium_losses)/len(losing_trades)*100:.1f}%)")
        print(f"  >15 min: {len(long_losses)} ({len(long_losses)/len(losing_trades)*100:.1f}%)")
    
    def _calculate_signal_quality(self, analysis: Dict) -> float:
        """
        Calcule le score de qualité du signal (0-100)
        
        Basé sur:
        - Confluence d'indicateurs (20%)
        - Proximité support/résistance (25%)
        - Volume relatif (15%)
        - Spread bid/ask (10%)
        - Momentum short-term (15%)
        - Order book imbalance (15%)
        """
        score = 0.0
        
        # 1. Confluence d'indicateurs (20%)
        signal_details = analysis.get('signal_details', {})
        buy_signals = signal_details.get('buy_signals', 0)
        sell_signals = signal_details.get('sell_signals', 0)
        total_signals = buy_signals + sell_signals
        if total_signals > 0:
            confluence_score = min(total_signals / 10.0, 1.0) * 20
            score += confluence_score
        
        # 2. Proximité support/résistance (25%)
        current_price = analysis.get('current_price', 0)
        key_levels = analysis.get('advanced_analysis', {}).get('key_levels', {})
        supports = key_levels.get('supports', [])
        resistances = key_levels.get('resistances', [])
        
        min_distance = float('inf')
        for support in supports:
            if support > 0:
                distance = abs(current_price - support) / current_price * 100
                min_distance = min(min_distance, distance)
        for resistance in resistances:
            if resistance > 0:
                distance = abs(current_price - resistance) / current_price * 100
                min_distance = min(min_distance, distance)
        
        if min_distance < float('inf'):
            # Plus proche = meilleur score (max 0.5% = score 25)
            sr_score = max(0, 25 - (min_distance * 50))  # 0.5% = 25 points
            score += sr_score
        
        # 3. Volume relatif (15%)
        candles = analysis.get('candles', [])
        if len(candles) >= 20:
            recent_volume = sum(c.get('volume', 0) for c in candles[-5:])
            avg_volume = sum(c.get('volume', 0) for c in candles[-20:]) / 20
            if avg_volume > 0:
                volume_ratio = recent_volume / (avg_volume * 5)
                volume_score = min(volume_ratio / 1.5, 1.0) * 15  # 1.5x = 15 points
                score += volume_score
        
        # 4. Spread bid/ask (10%)
        # Spread faible = meilleur score
        spread = analysis.get('spread', 0.1)  # Par défaut 0.1%
        if spread < 0.05:  # Spread < 0.05% = 10 points
            spread_score = 10
        elif spread < 0.1:
            spread_score = 5
        else:
            spread_score = 0
        score += spread_score
        
        # 5. Momentum short-term (15%)
        momentum = analysis.get('advanced_analysis', {}).get('momentum', {})
        momentum_percent = abs(momentum.get('momentum_percent', 0))
        momentum_score = min(momentum_percent / 2.0, 1.0) * 15  # 2% = 15 points
        score += momentum_score
        
        # 6. Order book imbalance (15%)
        order_book = analysis.get('advanced_analysis', {}).get('order_book', {})
        imbalance = abs(order_book.get('order_book_imbalance', 0))
        imbalance_score = min(imbalance / 20.0, 1.0) * 15  # 20% = 15 points
        score += imbalance_score
        
        return min(score, 100.0)
    
    def _should_enter_trade(self, analysis: Dict) -> Tuple[bool, str]:
        """Vérifie si on doit entrer dans le trade selon les filtres"""
        try:
            # Volume >150% moyenne
            candles = analysis.get('candles', [])
            if len(candles) >= 20:
                recent_volume = sum(c.get('volume', 0) for c in candles[-5:])
                avg_volume = sum(c.get('volume', 0) for c in candles[-20:]) / 20
                if avg_volume > 0:
                    volume_ratio = recent_volume / (avg_volume * 5)
                    min_volume = getattr(config, 'MIN_VOLUME_MULTIPLIER', 1.5) if config else 1.5
                    if volume_ratio < min_volume:
                        return False, f"Volume insuffisant: {volume_ratio:.2f}x (min: {min_volume}x)"
                # Si avg_volume == 0, on passe (pas de filtre volume)
            
            # ATR dans range acceptable
            atr = analysis.get('indicators', {}).get('atr', 0)
            current_price = analysis.get('current_price', 0)
            if current_price > 0 and atr > 0:
                atr_percent = (atr / current_price) * 100
                atr_min = getattr(config, 'ATR_MIN_PERCENT', 0.4) if config else 0.4
                atr_max = getattr(config, 'ATR_MAX_PERCENT', 1.2) if config else 1.2
                if atr_percent < atr_min:
                    return False, f"ATR trop faible: {atr_percent:.2f}%"
                if atr_percent > atr_max:
                    return False, f"ATR trop élevé: {atr_percent:.2f}%"
            
            # Spread <0.05%
            spread = analysis.get('spread', 0.1)
            max_spread = getattr(config, 'MAX_SPREAD_PERCENT', 0.05) if config else 0.05
            if spread > max_spread:
                return False, f"Spread trop élevé: {spread:.3f}%"
            
            return True, "OK"
            
        except Exception as e:
            logger.error(f"Erreur dans should_enter_trade: {e}")
            return False, f"Erreur: {e}"
    
    def _calculate_metrics(self) -> Dict:
        """Calcule les métriques finales du backtest"""
        if not self.closed_trades:
            return {
                'error': 'Aucun trade exécuté',
                'total_trades': 0
            }
        
        trades = self.closed_trades
        total_trades = len(trades)
        
        winning_trades = [t for t in trades if t['pnl_net'] > 0]
        losing_trades = [t for t in trades if t['pnl_net'] <= 0]
        
        wins = len(winning_trades)
        losses = len(losing_trades)
        winrate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        avg_win = sum(t['pnl_net'] for t in winning_trades) / wins if wins > 0 else 0
        avg_loss = sum(t['pnl_net'] for t in losing_trades) / losses if losses > 0 else 0
        
        total_pnl = sum(t['pnl_net'] for t in trades)
        total_fees = sum(t['fees'] for t in trades)
        
        gross_profit = sum(t['pnl_net'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl_net'] for t in losing_trades))
        
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
        final_return = ((self.equity - self.initial_capital) / self.initial_capital) * 100
        
        # Sharpe Ratio (simplifié)
        returns = [t['pnl_percent'] for t in trades]
        if len(returns) > 1:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe_ratio = (avg_return / std_return) * np.sqrt(252) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': wins,
            'losing_trades': losses,
            'winrate': winrate,
            'profit_factor': profit_factor,
            'total_pnl': total_pnl,
            'roi': final_return,
            'initial_capital': self.initial_capital,
            'final_capital': self.equity,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_drawdown': self.max_drawdown * 100,
            'sharpe_ratio': sharpe_ratio,
            'total_fees': total_fees,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'trades': trades[-50:],  # 50 derniers trades
            'equity_curve': self.equity_curve
        }
    
    def print_detailed_metrics(self):
        """Affiche les métriques détaillées du backtest"""
        if not self.closed_trades:
            print("❌ Aucun trade")
            return
        
        winning_trades = [t for t in self.closed_trades if t['pnl_net'] > 0]
        losing_trades = [t for t in self.closed_trades if t['pnl_net'] <= 0]
        
        total_trades = len(self.closed_trades)
        wins = len(winning_trades)
        losses = len(losing_trades)
        
        winrate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        avg_win = sum(t['pnl_net'] for t in winning_trades) / wins if wins > 0 else 0
        avg_loss = sum(t['pnl_net'] for t in losing_trades) / losses if losses > 0 else 0
        
        total_pnl = sum(t['pnl_net'] for t in self.closed_trades)
        total_fees = sum(t['fees'] for t in self.closed_trades)
        
        gross_profit = sum(t['pnl_net'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl_net'] for t in losing_trades))
        
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
        final_return = ((self.equity - self.initial_capital) / self.initial_capital) * 100
        
        print("\n" + "="*60)
        print("📊 RÉSULTATS BACKTEST")
        print("="*60)
        print(f"Capital initial : ${self.initial_capital:,.2f}")
        print(f"Capital final   : ${self.equity:,.2f}")
        print(f"P&L Net         : ${total_pnl:,.2f} ({final_return:+.2f}%)")
        print(f"Frais totaux    : ${total_fees:,.2f}")
        print("-"*60)
        print(f"Total trades    : {total_trades}")
        print(f"Gagnants        : {wins} ({winrate:.2f}%)")
        print(f"Perdants        : {losses}")
        print(f"Profit Factor   : {profit_factor:.2f}")
        print("-"*60)
        print(f"Gain moyen      : ${avg_win:,.2f}")
        print(f"Perte moyenne   : ${avg_loss:,.2f}")
        print(f"Max Drawdown    : {self.max_drawdown*100:.2f}%")
        print("="*60)
        
        print("\n✅ VALIDATION:")
        print(f"  Winrate >45%     : {'✅' if winrate > 45 else '❌'} ({winrate:.1f}%)")
        print(f"  Profit Factor>1.2: {'✅' if profit_factor > 1.2 else '❌'} ({profit_factor:.2f})")
        print(f"  Drawdown <15%    : {'✅' if self.max_drawdown < 0.15 else '❌'} ({self.max_drawdown*100:.1f}%)")
        print(f"  Return >0%       : {'✅' if final_return > 0 else '❌'} ({final_return:+.1f}%)")
    
    def optimize_parameters(self, coin: str, param_ranges: Dict) -> Tuple[Optional[Dict], Optional[Dict], List]:
        """
        Grid search pour trouver meilleurs paramètres
        
        Args:
            coin: Symbole de la crypto
            param_ranges: Dict avec ranges de paramètres à tester
        
        Returns:
            (best_params, best_metrics, all_results)
        """
        from itertools import product
        
        best_profit_factor = 0
        best_params = None
        best_metrics = None
        
        # Générer combinaisons
        param_names = list(param_ranges.keys())
        param_values = [param_ranges[k] for k in param_names]
        
        results = []
        total_combinations = 1
        for v in param_values:
            total_combinations *= len(v)
        
        logger.info(f"🔍 Grid search: {total_combinations} combinaisons à tester...")
        
        for idx, values in enumerate(product(*param_values), 1):
            params = dict(zip(param_names, values))
            
            logger.info(f"Test {idx}/{total_combinations}: {params}")
            
            # Appliquer paramètres temporairement
            original_config = {}
            try:
                import config
                for key, value in params.items():
                    config_key = key.upper()
                    if hasattr(config, config_key):
                        original_config[config_key] = getattr(config, config_key)
                        setattr(config, config_key, value)
            except Exception as e:
                logger.error(f"Erreur application paramètres: {e}")
            
            # Run backtest
            self.reset()
            metrics = self.run(coin=coin)
            
            # Restaurer config
            try:
                import config
                for key, value in original_config.items():
                    setattr(config, key, value)
            except:
                pass
            
            # Enregistrer
            result = {
                'params': params.copy(),
                'winrate': metrics.get('winrate', 0),
                'profit_factor': metrics.get('profit_factor', 0),
                'roi': metrics.get('roi', 0),
                'max_drawdown': metrics.get('max_drawdown', 0),
                'total_trades': metrics.get('total_trades', 0)
            }
            results.append(result)
            
            # Meilleur ?
            pf = metrics.get('profit_factor', 0)
            wr = metrics.get('winrate', 0)
            dd = metrics.get('max_drawdown', 0)
            
            if pf > best_profit_factor and wr > 45 and dd < 15:
                best_profit_factor = pf
                best_params = params
                best_metrics = metrics
        
        return best_params, best_metrics, results
    
    def reset(self):
        """Réinitialise le backtest pour un nouveau run"""
        self.capital = self.initial_capital
        self.equity = self.initial_capital
        self.equity_curve = []
        self.closed_trades = []
        self.positions = {}
        self.max_drawdown = 0.0
        self.max_equity = self.initial_capital
    
    def generate_report(self, output_file: str = "backtest_report.html") -> str:
        """Génère un rapport HTML avec equity curve et métriques"""
        metrics = self._calculate_metrics()
        
        if 'error' in metrics:
            return f"<html><body><h1>Erreur: {metrics['error']}</h1></body></html>"
        
        # Créer l'equity curve
        equity_html = ""
        if self.equity_curve:
            equity_data = self.equity_curve
            # Générer un graphique simple en HTML/CSS
            equity_html = f"""
            <div style="margin: 20px;">
                <h2>Equity Curve</h2>
                <div style="width: 100%; height: 400px; border: 1px solid #ccc;">
                    <!-- Graphique sera généré par JavaScript ou matplotlib -->
                </div>
            </div>
            """
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Backtest Report - Scalping Strategy</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .metric {{ display: inline-block; margin: 10px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
                .metric-label {{ font-size: 12px; color: #7f8c8d; }}
                .positive {{ color: #27ae60; }}
                .negative {{ color: #e74c3c; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #3498db; color: white; }}
            </style>
        </head>
        <body>
            <h1>📊 Rapport de Backtest - Stratégie Scalping</h1>
            
            <h2>📈 Métriques Principales</h2>
            <div class="metric">
                <div class="metric-label">Winrate</div>
                <div class="metric-value {'positive' if metrics['winrate'] >= 55 else 'negative'}">{metrics['winrate']:.2f}%</div>
            </div>
            <div class="metric">
                <div class="metric-label">Profit Factor</div>
                <div class="metric-value {'positive' if metrics['profit_factor'] >= 1.3 else 'negative'}">{metrics['profit_factor']:.2f}</div>
            </div>
            <div class="metric">
                <div class="metric-label">ROI</div>
                <div class="metric-value {'positive' if metrics['roi'] > 0 else 'negative'}">{metrics['roi']:.2f}%</div>
            </div>
            <div class="metric">
                <div class="metric-label">Max Drawdown</div>
                <div class="metric-value {'negative' if metrics['max_drawdown'] > 12 else 'positive'}">{metrics['max_drawdown']:.2f}%</div>
            </div>
            <div class="metric">
                <div class="metric-label">Total Trades</div>
                <div class="metric-value">{metrics['total_trades']}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Sharpe Ratio</div>
                <div class="metric-value">{metrics['sharpe_ratio']:.2f}</div>
            </div>
            
            <h2>💰 PNL</h2>
            <div class="metric">
                <div class="metric-label">Capital Initial</div>
                <div class="metric-value">${metrics['initial_capital']:,.2f}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Capital Final</div>
                <div class="metric-value {'positive' if metrics['final_capital'] > metrics['initial_capital'] else 'negative'}">${metrics['final_capital']:,.2f}</div>
            </div>
            <div class="metric">
                <div class="metric-label">PNL Total</div>
                <div class="metric-value {'positive' if metrics['total_pnl'] > 0 else 'negative'}">${metrics['total_pnl']:,.2f}</div>
            </div>
            
            <h2>📊 Détails des Trades</h2>
            <table>
                <tr>
                    <th>Coin</th>
                    <th>Side</th>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th>Size</th>
                    <th>PNL</th>
                    <th>PNL %</th>
                    <th>Reason</th>
                </tr>
        """
        
        for trade in metrics.get('trades', [])[-20:]:  # 20 derniers
            pnl_class = 'positive' if trade['pnl_net'] > 0 else 'negative'
            html += f"""
                <tr>
                    <td>{trade.get('coin', 'N/A')}</td>
                    <td>{trade.get('side', 'N/A')}</td>
                    <td>${trade.get('entry_price', 0):.2f}</td>
                    <td>${trade.get('exit_price', 0):.2f}</td>
                    <td>${trade.get('size', 0):.2f}</td>
                    <td class="{pnl_class}">${trade['pnl_net']:,.2f}</td>
                    <td class="{pnl_class}">{trade['pnl_percent']:+.2f}%</td>
                    <td>{trade.get('reason', 'N/A')}</td>
                </tr>
            """
        
        html += """
            </table>
        </body>
        </html>
        """
        
        # Sauvegarder le rapport
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info(f"✅ Rapport généré: {output_file}")
        except Exception as e:
            logger.error(f"Erreur génération rapport: {e}")
        
        return html


# Exemple d'utilisation
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    backtest = ScalpingBacktest(initial_capital=10000)
    
    results = backtest.run(coin="BTC")
    
    if 'error' not in results:
        print(f"\n📊 Résultats du Backtest:")
        print(f"   Winrate: {results['winrate']:.2f}%")
        print(f"   Profit Factor: {results['profit_factor']:.2f}")
        print(f"   ROI: {results['roi']:.2f}%")
        print(f"   Max Drawdown: {results['max_drawdown']:.2f}%")
        print(f"   Total Trades: {results['total_trades']}")
        
        # Générer le rapport
        backtest.generate_report("backtest_report.html")
    else:
        print(f"❌ Erreur: {results['error']}")

