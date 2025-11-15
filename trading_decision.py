"""
Système de décision de trading automatisé
Détermine où, quand et avec quelles règles rentrer en position
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from hyperliquid_signals import HyperliquidSignalGenerator
import config

logger = logging.getLogger(__name__)

class TradingDecisionEngine:
    """
    Moteur de décision pour déterminer les entrées en position
    """
    
    def __init__(self):
        self.entry_rules = self._load_entry_rules()
        self.min_signal_quality = getattr(config, 'SIGNAL_QUALITY_THRESHOLD', 78)
        self.min_risk_reward = getattr(config, 'MIN_RISK_REWARD_RATIO', 2.0)
        
    def _load_entry_rules(self) -> Dict:
        """Charge les règles d'entrée optimisées"""
        return {
            # RÈGLES DE QUALITÉ DU SIGNAL
            'min_signal_quality': getattr(config, 'SIGNAL_QUALITY_THRESHOLD', 78),
            'min_buy_signals': 3,  # Réduit de 4 à 3 pour plus de flexibilité
            'min_sell_signals': 3,  # Réduit de 4 à 3 pour plus de flexibilité
            'signal_dominance': 1,  # Réduit de 2 à 1 pour plus de flexibilité
            
            # RÈGLES DE CONFLUENCE
            'min_confluence_score': 60,  # Score de confluence minimum
            'require_trend_alignment': True,  # Alignement avec la tendance
            'require_volume_confirmation': True,  # Confirmation par le volume
            
            # RÈGLES DE VOLUME
            'min_volume_ratio': getattr(config, 'MIN_VOLUME_MULTIPLIER', 2.2),
            'max_spread_percent': getattr(config, 'MAX_SPREAD_PERCENT', 0.03),
            
            # RÈGLES DE VOLATILITÉ
            'atr_min_percent': getattr(config, 'ATR_MIN_PERCENT', 0.5) / 100,
            'atr_max_percent': getattr(config, 'ATR_MAX_PERCENT', 1.2) / 100,
            
            # RÈGLES DE PROXIMITÉ SUPPORT/RÉSISTANCE
            'min_distance_sr_percent': getattr(config, 'MIN_DISTANCE_SR_PERCENT', 0.3) / 100,
            'prefer_sr_proximity': True,  # Préférer les entrées près des S/R
            
            # RÈGLES DE RISQUE
            'max_stop_loss_percent': getattr(config, 'MAX_STOP_LOSS_PERCENT', 0.8) / 100,
            'min_stop_loss_percent': getattr(config, 'MIN_STOP_LOSS_PERCENT', 0.5) / 100,
            'min_risk_reward_ratio': getattr(config, 'MIN_RISK_REWARD_RATIO', 2.0),
            
            # RÈGLES DE TIMING
            'avoid_low_liquidity_hours': True,
            'require_momentum_confirmation': True,
            
            # RÈGLES DE CONTEXTE
            'require_macd_alignment': True,
            'require_ema_alignment': True,
            'min_rsi_divergence': 5,  # Éviter RSI trop proche de 50
        }
    
    def evaluate_entry_opportunity(
        self, 
        coin: str, 
        analysis: Dict,
        current_positions: Dict = None,
        debug: bool = False
    ) -> Tuple[bool, Dict, float, Dict]:
        """
        Évalue une opportunité d'entrée en position
        
        Returns:
            (should_enter, order_details, confidence_score, rejection_reasons)
        """
        rejection_reasons = {}
        
        if current_positions is None:
            current_positions = {}
        
        # Vérifier si position déjà ouverte
        if coin in current_positions:
            rejection_reasons['position_exists'] = f"Position déjà ouverte pour {coin}"
            return False, {}, 0.0, rejection_reasons
        
        signal = analysis.get('signal', 'NEUTRE')
        if signal == 'NEUTRE':
            rejection_reasons['signal_neutral'] = "Signal NEUTRE"
            return False, {}, 0.0, rejection_reasons
        
        signal_quality = analysis.get('signal_quality', 0)
        signal_details = analysis.get('signal_details', {})
        buy_signals = signal_details.get('buy_signals', 0)
        sell_signals = signal_details.get('sell_signals', 0)
        current_price = analysis.get('current_price', 0)
        
        if current_price == 0:
            rejection_reasons['no_price'] = "Prix actuel = 0"
            return False, {}, 0.0, rejection_reasons
        
        # Score de confiance initial
        confidence_score = 0.0
        reasons = []
        
        # 1. QUALITÉ DU SIGNAL (30 points)
        if signal_quality >= self.entry_rules['min_signal_quality']:
            quality_score = min(30, (signal_quality - self.entry_rules['min_signal_quality']) / 2)
            confidence_score += quality_score
            reasons.append(f"Qualité signal: {signal_quality:.1f}/100")
        else:
            rejection_reasons['signal_quality'] = f"Qualité {signal_quality:.1f} < {self.entry_rules['min_signal_quality']}"
            return False, {}, 0.0, rejection_reasons
        
        # 2. CONFLUENCE DES SIGNAUX (25 points)
        if signal == 'ACHAT':
            if buy_signals >= self.entry_rules['min_buy_signals']:
                signal_diff = buy_signals - sell_signals
                if signal_diff >= self.entry_rules['signal_dominance']:
                    confluence_score = min(25, signal_diff * 3)
                    confidence_score += confluence_score
                    reasons.append(f"Confluence achat: {buy_signals} vs {sell_signals}")
                else:
                    rejection_reasons['confluence_dominance'] = f"Différence insuffisante: {signal_diff} < {self.entry_rules['signal_dominance']}"
            else:
                rejection_reasons['confluence_buy_signals'] = f"Signaux achat {buy_signals} < {self.entry_rules['min_buy_signals']}"
        else:  # VENTE
            if sell_signals >= self.entry_rules['min_sell_signals']:
                signal_diff = sell_signals - buy_signals
                if signal_diff >= self.entry_rules['signal_dominance']:
                    confluence_score = min(25, signal_diff * 3)
                    confidence_score += confluence_score
                    reasons.append(f"Confluence vente: {sell_signals} vs {buy_signals}")
                else:
                    rejection_reasons['confluence_dominance'] = f"Différence insuffisante: {signal_diff} < {self.entry_rules['signal_dominance']}"
            else:
                rejection_reasons['confluence_sell_signals'] = f"Signaux vente {sell_signals} < {self.entry_rules['min_sell_signals']}"
        
        # 3. VOLUME (15 points)
        volume_ratio = analysis.get('volume_ratio', 0)
        if volume_ratio >= self.entry_rules['min_volume_ratio']:
            volume_score = min(15, (volume_ratio - self.entry_rules['min_volume_ratio']) * 5)
            confidence_score += volume_score
            reasons.append(f"Volume confirmé: {volume_ratio:.2f}x")
        else:
            rejection_reasons['volume'] = f"Volume ratio {volume_ratio:.2f} < {self.entry_rules['min_volume_ratio']}"
        
        # 4. INDICATEURS TECHNIQUES (20 points)
        indicators = analysis.get('indicators', {})
        rsi = indicators.get('rsi', 50)
        macd = indicators.get('macd', {})
        ema20 = indicators.get('ema20', 0)
        ema50 = indicators.get('ema50', 0)
        
        # Alignement EMA
        if ema20 > 0 and ema50 > 0:
            if signal == 'ACHAT' and current_price > ema20 > ema50:
                confidence_score += 8
                reasons.append("Prix > EMA20 > EMA50 (tendance haussière)")
            elif signal == 'VENTE' and current_price < ema20 < ema50:
                confidence_score += 8
                reasons.append("Prix < EMA20 < EMA50 (tendance baissière)")
        
        # MACD
        macd_hist = macd.get('histogram', 0)
        if signal == 'ACHAT' and macd_hist > 0:
            confidence_score += 6
            reasons.append("MACD histogramme positif")
        elif signal == 'VENTE' and macd_hist < 0:
            confidence_score += 6
            reasons.append("MACD histogramme négatif")
        
        # RSI divergence
        if signal == 'ACHAT' and rsi < 50:
            rsi_score = min(6, (50 - rsi) / 5)
            confidence_score += rsi_score
        elif signal == 'VENTE' and rsi > 50:
            rsi_score = min(6, (rsi - 50) / 5)
            confidence_score += rsi_score
        
        # 5. PROXIMITÉ SUPPORT/RÉSISTANCE (10 points)
        key_levels = analysis.get('advanced_analysis', {}).get('key_levels', {})
        supports = key_levels.get('supports', [])
        resistances = key_levels.get('resistances', [])
        
        if signal == 'ACHAT' and supports:
            min_distance = min([abs(current_price - s) / current_price for s in supports[:3] if s > 0], default=1.0)
            if min_distance <= self.entry_rules['min_distance_sr_percent'] * 2:
                sr_score = min(10, (1 - min_distance / (self.entry_rules['min_distance_sr_percent'] * 2)) * 10)
                confidence_score += sr_score
                reasons.append(f"Proche support: {min_distance*100:.2f}%")
        
        if signal == 'VENTE' and resistances:
            min_distance = min([abs(current_price - r) / current_price for r in resistances[:3] if r > 0], default=1.0)
            if min_distance <= self.entry_rules['min_distance_sr_percent'] * 2:
                sr_score = min(10, (1 - min_distance / (self.entry_rules['min_distance_sr_percent'] * 2)) * 10)
                confidence_score += sr_score
                reasons.append(f"Proche résistance: {min_distance*100:.2f}%")
        
        # 6. SPREAD ET LIQUIDITÉ (5 points)
        spread = analysis.get('spread', 0.1)
        if spread <= self.entry_rules['max_spread_percent']:
            confidence_score += 5
            reasons.append(f"Spread acceptable: {spread*100:.3f}%")
        else:
            rejection_reasons['spread'] = f"Spread {spread*100:.3f}% > {self.entry_rules['max_spread_percent']*100:.3f}%"
        
        # 7. VOLATILITÉ (5 points)
        atr = indicators.get('atr', 0)
        if atr > 0:
            atr_percent = atr / current_price
            if self.entry_rules['atr_min_percent'] <= atr_percent <= self.entry_rules['atr_max_percent']:
                confidence_score += 5
                reasons.append(f"ATR optimal: {atr_percent*100:.2f}%")
            else:
                rejection_reasons['atr'] = f"ATR {atr_percent*100:.2f}% hors range [{self.entry_rules['atr_min_percent']*100:.2f}%, {self.entry_rules['atr_max_percent']*100:.2f}%]"
        else:
            rejection_reasons['atr'] = "ATR = 0"
        
        # Calculer SL/TP
        sl_tp = self._calculate_sl_tp(signal, current_price, analysis)
        
        # Vérifier le ratio risque/récompense
        if sl_tp['risk_reward_ratio'] < self.entry_rules['min_risk_reward_ratio']:
            rejection_reasons['risk_reward'] = f"R/R {sl_tp['risk_reward_ratio']:.2f} < {self.entry_rules['min_risk_reward_ratio']}"
            return False, {}, confidence_score, rejection_reasons
        
        # Score minimum pour entrer
        min_confidence = 55.0  # Réduit de 60 à 55 pour compenser le seuil qualité réduit
        
        if confidence_score >= min_confidence:
            order_details = {
                'coin': coin,
                'signal': signal,
                'entry_price': current_price,
                'stop_loss': sl_tp['stop_loss'],
                'take_profit': sl_tp['take_profit'],
                'stop_loss_percent': sl_tp['stop_loss_percent'],
                'take_profit_percent': sl_tp['take_profit_percent'],
                'risk_reward_ratio': sl_tp['risk_reward_ratio'],
                'confidence_score': confidence_score,
                'reasons': reasons,
                'signal_quality': signal_quality,
                'buy_signals': buy_signals,
                'sell_signals': sell_signals,
                'timestamp': datetime.now().isoformat()
            }
            
            return True, order_details, confidence_score, {}
        
        rejection_reasons['confidence'] = f"Score confiance {confidence_score:.1f} < {min_confidence}"
        return False, {}, confidence_score, rejection_reasons
    
    def _calculate_sl_tp(self, signal: str, entry_price: float, analysis: Dict) -> Dict:
        """Calcule les niveaux de Stop Loss et Take Profit"""
        indicators = analysis.get('indicators', {})
        atr = indicators.get('atr', 0)
        
        # SL basé sur ATR ou pourcentage fixe
        if atr > 0:
            atr_percent = atr / entry_price
            sl_percent = max(
                self.entry_rules['min_stop_loss_percent'],
                min(self.entry_rules['max_stop_loss_percent'], atr_percent * 1.2)
            )
        else:
            sl_percent = (self.entry_rules['min_stop_loss_percent'] + self.entry_rules['max_stop_loss_percent']) / 2
        
        # TP basé sur le ratio risque/récompense
        tp_percent = sl_percent * self.entry_rules['min_risk_reward_ratio']
        
        if signal == 'ACHAT':
            stop_loss = entry_price * (1 - sl_percent)
            take_profit = entry_price * (1 + tp_percent)
        else:  # VENTE
            stop_loss = entry_price * (1 + sl_percent)
            take_profit = entry_price * (1 - tp_percent)
        
        return {
            'stop_loss': round(stop_loss, 2),
            'take_profit': round(take_profit, 2),
            'stop_loss_percent': round(sl_percent * 100, 2),
            'take_profit_percent': round(tp_percent * 100, 2),
            'risk_reward_ratio': round(tp_percent / sl_percent, 2)
        }

