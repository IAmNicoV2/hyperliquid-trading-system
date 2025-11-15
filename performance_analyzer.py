"""
Analyseur de performance pour optimiser le système
Analyse les trades et propose des améliorations
"""

import logging
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
from order_manager import OrderManager

logger = logging.getLogger(__name__)

class PerformanceAnalyzer:
    """
    Analyse les performances et propose des optimisations
    """
    
    def __init__(self, order_manager: OrderManager):
        self.order_manager = order_manager
    
    def analyze_performance(self) -> Dict:
        """Analyse complète de la performance"""
        stats = self.order_manager.get_statistics()
        closed_positions = self.order_manager.closed_positions
        
        if not closed_positions:
            return {
                'stats': stats,
                'recommendations': ["Pas assez de données pour analyser"],
                'optimizations': []
            }
        
        analysis = {
            'stats': stats,
            'by_coin': self._analyze_by_coin(closed_positions),
            'by_signal_type': self._analyze_by_signal_type(closed_positions),
            'by_confidence': self._analyze_by_confidence(closed_positions),
            'by_time': self._analyze_by_time(closed_positions),
            'recommendations': [],
            'optimizations': []
        }
        
        # Générer des recommandations
        analysis['recommendations'] = self._generate_recommendations(analysis)
        analysis['optimizations'] = self._suggest_optimizations(analysis)
        
        return analysis
    
    def _analyze_by_coin(self, positions: List[Dict]) -> Dict:
        """Analyse par coin"""
        by_coin = {}
        for pos in positions:
            coin = pos['coin']
            if coin not in by_coin:
                by_coin[coin] = {'wins': 0, 'losses': 0, 'total_pnl': 0.0}
            
            if pos.get('pnl_percent', 0) > 0:
                by_coin[coin]['wins'] += 1
            else:
                by_coin[coin]['losses'] += 1
            
            by_coin[coin]['total_pnl'] += pos.get('pnl_percent', 0)
        
        # Calculer winrate par coin
        for coin in by_coin:
            total = by_coin[coin]['wins'] + by_coin[coin]['losses']
            by_coin[coin]['winrate'] = (by_coin[coin]['wins'] / total * 100) if total > 0 else 0.0
        
        return by_coin
    
    def _analyze_by_signal_type(self, positions: List[Dict]) -> Dict:
        """Analyse par type de signal (ACHAT/VENTE)"""
        by_type = {'ACHAT': {'wins': 0, 'losses': 0}, 'VENTE': {'wins': 0, 'losses': 0}}
        
        for pos in positions:
            signal_type = pos['signal']
            if pos.get('pnl_percent', 0) > 0:
                by_type[signal_type]['wins'] += 1
            else:
                by_type[signal_type]['losses'] += 1
        
        for signal_type in by_type:
            total = by_type[signal_type]['wins'] + by_type[signal_type]['losses']
            by_type[signal_type]['winrate'] = (by_type[signal_type]['wins'] / total * 100) if total > 0 else 0.0
        
        return by_type
    
    def _analyze_by_confidence(self, positions: List[Dict]) -> Dict:
        """Analyse par niveau de confiance"""
        confidence_ranges = {
            'high': {'min': 80, 'wins': 0, 'losses': 0},
            'medium': {'min': 60, 'max': 80, 'wins': 0, 'losses': 0},
            'low': {'max': 60, 'wins': 0, 'losses': 0}
        }
        
        for pos in positions:
            confidence = pos.get('confidence_score', 0)
            is_win = pos.get('pnl_percent', 0) > 0
            
            if confidence >= 80:
                if is_win:
                    confidence_ranges['high']['wins'] += 1
                else:
                    confidence_ranges['high']['losses'] += 1
            elif confidence >= 60:
                if is_win:
                    confidence_ranges['medium']['wins'] += 1
                else:
                    confidence_ranges['medium']['losses'] += 1
            else:
                if is_win:
                    confidence_ranges['low']['wins'] += 1
                else:
                    confidence_ranges['low']['losses'] += 1
        
        # Calculer winrate par niveau
        for level in confidence_ranges:
            total = confidence_ranges[level]['wins'] + confidence_ranges[level]['losses']
            confidence_ranges[level]['winrate'] = (confidence_ranges[level]['wins'] / total * 100) if total > 0 else 0.0
        
        return confidence_ranges
    
    def _analyze_by_time(self, positions: List[Dict]) -> Dict:
        """Analyse par période de la journée"""
        by_hour = {}
        for pos in positions:
            try:
                executed_at = datetime.fromisoformat(pos.get('executed_at', pos.get('created_at', '')))
                hour = executed_at.hour
                if hour not in by_hour:
                    by_hour[hour] = {'wins': 0, 'losses': 0}
                
                if pos.get('pnl_percent', 0) > 0:
                    by_hour[hour]['wins'] += 1
                else:
                    by_hour[hour]['losses'] += 1
            except:
                pass
        
        return by_hour
    
    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """Génère des recommandations basées sur l'analyse"""
        recommendations = []
        stats = analysis['stats']
        
        # Winrate
        if stats['winrate'] < 50:
            recommendations.append(f"⚠️ Winrate faible ({stats['winrate']:.1f}%) - Augmenter le seuil de confiance minimum")
        
        if stats['winrate'] >= 50 and stats['profit_factor'] < 1.3:
            recommendations.append(f"⚠️ Winrate OK mais Profit Factor faible ({stats['profit_factor']:.2f}) - Améliorer le ratio risque/récompense")
        
        # Analyse par coin
        by_coin = analysis['by_coin']
        worst_coin = min(by_coin.items(), key=lambda x: x[1].get('winrate', 0), default=None)
        best_coin = max(by_coin.items(), key=lambda x: x[1].get('winrate', 0), default=None)
        
        if worst_coin and worst_coin[1].get('winrate', 0) < 40:
            recommendations.append(f"⚠️ Éviter {worst_coin[0]} (winrate: {worst_coin[1]['winrate']:.1f}%)")
        
        if best_coin and best_coin[1].get('winrate', 0) > 60:
            recommendations.append(f"✅ Privilégier {best_coin[0]} (winrate: {best_coin[1]['winrate']:.1f}%)")
        
        # Analyse par type de signal
        by_type = analysis['by_signal_type']
        if by_type.get('ACHAT', {}).get('winrate', 0) < 45:
            recommendations.append("⚠️ Signaux ACHAT peu performants - Renforcer les filtres")
        if by_type.get('VENTE', {}).get('winrate', 0) < 45:
            recommendations.append("⚠️ Signaux VENTE peu performants - Renforcer les filtres")
        
        # Analyse par confiance
        by_confidence = analysis['by_confidence']
        if by_confidence.get('low', {}).get('winrate', 0) > 0:
            recommendations.append("⚠️ Éviter les ordres à faible confiance (<60)")
        
        if by_confidence.get('high', {}).get('winrate', 0) > 60:
            recommendations.append("✅ Augmenter le seuil minimum de confiance à 80")
        
        return recommendations
    
    def _suggest_optimizations(self, analysis: Dict) -> List[Dict]:
        """Suggère des optimisations de paramètres"""
        optimizations = []
        stats = analysis['stats']
        
        # Si winrate < 50, augmenter les seuils
        if stats['winrate'] < 50:
            optimizations.append({
                'parameter': 'min_confidence_score',
                'current': 60,
                'suggested': 70,
                'reason': f"Winrate actuel: {stats['winrate']:.1f}% - Augmenter le seuil de confiance"
            })
            
            optimizations.append({
                'parameter': 'min_signal_quality',
                'current': 78,
                'suggested': 82,
                'reason': "Améliorer la qualité des signaux acceptés"
            })
        
        # Si profit factor < 1.3, améliorer le ratio R/R
        if stats['profit_factor'] < 1.3:
            optimizations.append({
                'parameter': 'min_risk_reward_ratio',
                'current': 2.0,
                'suggested': 2.5,
                'reason': f"Profit Factor actuel: {stats['profit_factor']:.2f} - Améliorer le ratio R/R"
            })
        
        # Analyse par coin
        by_coin = analysis['by_coin']
        for coin, data in by_coin.items():
            if data.get('winrate', 0) < 40:
                optimizations.append({
                    'parameter': f'exclude_coin_{coin}',
                    'current': False,
                    'suggested': True,
                    'reason': f"Winrate {coin}: {data['winrate']:.1f}% - Exclure temporairement"
                })
        
        return optimizations

