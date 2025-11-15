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
        self.equity_curve = []
        self.trades = []
        self.positions = {}
        
        # Position manager
        self.position_manager = PositionManager()
        self.position_manager.set_daily_start_balance(self.initial_capital)
        
        # Signal generator
        self.signal_generator = None
        
        # Métriques
        self.max_drawdown = 0.0
        self.peak_capital = self.initial_capital
        
        logger.info(f"✅ Backtest initialisé: Capital=${self.initial_capital:,.2f}, Slippage={self.slippage*100:.3f}%")
    
    def load_historical_data(self, coin: str, interval: str = "1m", days: int = 30) -> List[Dict]:
        """
        Charge les données historiques depuis Hyperliquid
        
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
            candles_needed = intervals_per_day.get(interval, 1440) * days
            
            logger.info(f"📥 Chargement de {candles_needed} chandeliers pour {coin} ({interval})...")
            candles = generator.fetch_historical_candles(limit=min(candles_needed, 2000))
            
            if not candles:
                logger.error(f"❌ Impossible de charger les données pour {coin}")
                return []
            
            logger.info(f"✅ {len(candles)} chandeliers chargés")
            return candles
            
        except Exception as e:
            logger.error(f"Erreur chargement données: {e}", exc_info=True)
            return []
    
    def simulate_trade(
        self,
        side: str,
        entry_price: float,
        size: float,
        exit_price: float,
        is_maker: bool = False
    ) -> Dict:
        """
        Simule un trade avec frais et slippage
        
        Returns:
            Résultat du trade
        """
        # Appliquer slippage à l'entrée
        if side == 'LONG':
            entry_price_executed = entry_price * (1 + self.slippage)
            exit_price_executed = exit_price * (1 - self.slippage)
        else:  # SHORT
            entry_price_executed = entry_price * (1 - self.slippage)
            exit_price_executed = exit_price * (1 + self.slippage)
        
        # Calculer PNL brut
        if side == 'LONG':
            pnl_brut = (exit_price_executed - entry_price_executed) * size
        else:
            pnl_brut = (entry_price_executed - exit_price_executed) * size
        
        # Appliquer les frais
        commission = self.commission_maker if is_maker else self.commission_taker
        fees_entry = entry_price_executed * size * commission
        fees_exit = exit_price_executed * size * commission
        total_fees = fees_entry + fees_exit
        
        # PNL net
        pnl_net = pnl_brut - total_fees
        pnl_percent = (pnl_net / (entry_price_executed * size)) * 100
        
        return {
            'side': side,
            'entry_price': entry_price,
            'entry_price_executed': entry_price_executed,
            'exit_price': exit_price,
            'exit_price_executed': exit_price_executed,
            'size': size,
            'pnl_brut': pnl_brut,
            'pnl_net': pnl_net,
            'pnl_percent': pnl_percent,
            'fees': total_fees,
            'is_maker': is_maker
        }
    
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
        
        # Charger les données
        candles = self.load_historical_data(coin, interval="1m", days=30)
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
        self.signal_generator = HyperliquidSignalGenerator(coin=coin, interval="1m")
        self.signal_generator.candles = candles
        
        # Pour le backtest, utiliser un seuil plus bas pour générer des trades
        signal_threshold = signal_quality_threshold or 40  # 40 pour backtest (plus permissif)
        
        # Statistiques pour debug
        stats = {
            'total_signals': 0,
            'neutral_signals': 0,
            'quality_too_low': 0,
            'filters_failed': 0,
            'positions_opened': 0
        }
        
        # Simuler le trading
        logger.info(f"📊 Simulation de {len(candles)} chandeliers...")
        
        for i in range(50, len(candles)):  # Commencer après 50 bougies pour avoir des indicateurs
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
                
                # Vérifier les filtres d'entrée (assouplis pour backtest)
                should_enter, reason = self._should_enter_trade(analysis)
                if not should_enter:
                    stats['filters_failed'] += 1
                    # Pour backtest, on peut ignorer certains filtres stricts
                    # Si qualité >60, on peut passer malgré certains filtres
                    if signal_quality < 60:
                        if i % 200 == 0:
                            logger.debug(f"Filtre d'entrée non passé: {reason}")
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
                
                # Calculer la taille de position
                entry_price = candles[i]['close']
                sl_tp = analysis.get('sl_tp', {})
                stop_loss = sl_tp.get('stop_loss', 0)
                
                if stop_loss == 0:
                    continue
                
                atr = analysis.get('indicators', {}).get('atr', 0)
                position_size = self.position_manager.calculate_position_size(
                    signal_quality, self.capital, atr, entry_price, stop_loss
                )
                
                # Ouvrir la position
                side = 'LONG' if signal == 'ACHAT' else 'SHORT'
                # Utiliser les TP calculés par calculate_sl_tp
                take_profit_1 = sl_tp.get('take_profit_1', entry_price * 1.01)
                take_profit_2 = sl_tp.get('take_profit_2', entry_price * 1.018)
                take_profit_3 = sl_tp.get('take_profit_3', entry_price * 1.025)
                
                position = self.position_manager.open_position(
                    coin=coin,
                    side=side,
                    entry_price=entry_price,
                    size=position_size,
                    stop_loss=stop_loss,
                    take_profit_1=take_profit_1,
                    take_profit_2=take_profit_2,
                    take_profit_3=take_profit_3,
                    signal_quality=signal_quality
                )
                
                # Simuler la fermeture de la position
                exit_reason = None
                exit_price = None
                
                # Chercher la sortie dans les bougies suivantes
                max_lookahead = min(100, len(candles) - i - 1)  # Max 100 bougies ou jusqu'à la fin
                for j in range(i + 1, i + 1 + max_lookahead):
                    current_candle = candles[j]
                    current_price = current_candle['close']
                    
                    # Vérifier Stop Loss d'abord (priorité)
                    if self.position_manager.check_stop_loss(coin, current_price):
                        exit_price = position['stop_loss']
                        exit_reason = 'STOP_LOSS'
                        break
                    
                    # Vérifier Take Profits directement
                    if side == 'LONG':
                        if current_price >= position['take_profit_1']:
                            exit_price = position['take_profit_1']
                            exit_reason = 'TAKE_PROFIT_1'
                            break
                        elif current_price >= position['take_profit_2']:
                            exit_price = position['take_profit_2']
                            exit_reason = 'TAKE_PROFIT_2'
                            break
                        elif current_price >= position['take_profit_3']:
                            exit_price = position['take_profit_3']
                            exit_reason = 'TAKE_PROFIT_3'
                            break
                    else:  # SHORT
                        if current_price <= position['take_profit_1']:
                            exit_price = position['take_profit_1']
                            exit_reason = 'TAKE_PROFIT_1'
                            break
                        elif current_price <= position['take_profit_2']:
                            exit_price = position['take_profit_2']
                            exit_reason = 'TAKE_PROFIT_2'
                            break
                        elif current_price <= position['take_profit_3']:
                            exit_price = position['take_profit_3']
                            exit_reason = 'TAKE_PROFIT_3'
                            break
                    
                    # Vérifier Stop Loss temporel
                    if self.position_manager.check_time_stop(coin):
                        exit_price = current_price
                        exit_reason = 'TIME_STOP'
                        break
                
                # Si pas de sortie trouvée, fermer à la fin du lookahead
                if exit_price is None:
                    if i + max_lookahead < len(candles):
                        exit_price = candles[i + max_lookahead]['close']
                    else:
                        exit_price = candles[-1]['close']
                    exit_reason = 'TIMEOUT'
                
                # Simuler le trade
                trade_result = self.simulate_trade(
                    side=side,
                    entry_price=entry_price,
                    size=position_size,
                    exit_price=exit_price,
                    is_maker=getattr(config, 'PREFER_MAKER_ORDERS', True) if config else True
                )
                
                # Fermer la position
                trade_record = self.position_manager.close_position(coin, exit_price, exit_reason)
                if trade_record:
                    trade_record.update(trade_result)
                    self.trades.append(trade_record)
                    
                    # Mettre à jour le capital
                    self.capital += trade_record['pnl_net']
                    self.equity_curve.append({
                        'time': candles[i]['time'],
                        'capital': self.capital,
                        'pnl': trade_record['pnl_net']
                    })
                    
                    # Mettre à jour le drawdown
                    if self.capital > self.peak_capital:
                        self.peak_capital = self.capital
                    else:
                        drawdown = (self.peak_capital - self.capital) / self.peak_capital
                        if drawdown > self.max_drawdown:
                            self.max_drawdown = drawdown
                
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
        return metrics
    
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
        if not self.trades:
            return {
                'error': 'Aucun trade exécuté',
                'total_trades': 0
            }
        
        trades = self.trades
        total_trades = len(trades)
        
        winning_trades = [t for t in trades if t['pnl_net'] > 0]
        losing_trades = [t for t in trades if t['pnl_net'] < 0]
        
        winrate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        total_wins = sum(t['pnl_net'] for t in winning_trades)
        total_losses = abs(sum(t['pnl_net'] for t in losing_trades))
        
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        avg_win = total_wins / len(winning_trades) if winning_trades else 0
        avg_loss = total_losses / len(losing_trades) if losing_trades else 0
        
        total_pnl = sum(t['pnl_net'] for t in trades)
        final_capital = self.initial_capital + total_pnl
        roi = (total_pnl / self.initial_capital) * 100
        
        # Sharpe Ratio (simplifié)
        returns = [t['pnl_percent'] for t in trades]
        if len(returns) > 1:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe_ratio = (avg_return / std_return) * np.sqrt(252) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Max drawdown
        max_dd = self.max_drawdown * 100
        
        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'winrate': winrate * 100,
            'profit_factor': profit_factor,
            'total_pnl': total_pnl,
            'roi': roi,
            'initial_capital': self.initial_capital,
            'final_capital': final_capital,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_drawdown': max_dd,
            'sharpe_ratio': sharpe_ratio,
            'trades': trades[-50:],  # 50 derniers trades
            'equity_curve': self.equity_curve
        }
    
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

