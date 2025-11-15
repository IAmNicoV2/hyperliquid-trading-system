# 📚 Documentation Technique - Système de Trading Hyperliquid

## 🏗️ Architecture

### Structure du Projet

```
.
├── hyperliquid_signals.py      # Moteur d'analyse et génération de signaux
├── hyperliquid_web_server.py   # Serveur web Flask pour l'interface
├── config.py                   # Configuration centralisée
├── requirements.txt            # Dépendances Python
├── DEMARRAGE_RAPIDE.md        # Guide de démarrage rapide
└── README_TECHNIQUE.md        # Cette documentation
```

## 🔧 Composants Principaux

### 1. HyperliquidSignalGenerator

Classe principale pour la génération de signaux de trading.

#### Méthodes Principales

- `fetch_historical_candles(limit=200)`: Récupère les chandeliers historiques avec retry logic
- `fetch_order_book()`: Récupère le carnet d'ordres avec gestion d'erreurs
- `analyze()`: Effectue une analyse complète et génère un signal
- `calculate_sl_tp()`: Calcule les niveaux de Stop Loss et Take Profit

#### Indicateurs Techniques Implémentés

1. **RSI (Relative Strength Index)**
   - Période: 14
   - Méthode: Wilder (moyenne mobile exponentielle)
   - Seuils: < 30 (survendu), > 70 (suracheté)

2. **MACD (Moving Average Convergence Divergence)**
   - EMA rapide: 12
   - EMA lente: 26
   - Ligne de signal: 9

3. **EMA (Exponential Moving Average)**
   - EMA 20 (court terme)
   - EMA 50 (long terme)

4. **Bollinger Bands**
   - Période: 20
   - Écart-type: 2
   - Correction de Bessel pour l'écart-type

5. **Volume Profile**
   - POC (Point of Control)
   - VAH (Value Area High)
   - VAL (Value Area Low)

6. **ATR (Average True Range)**
   - Période: 14
   - Mesure de volatilité

7. **Stochastic Oscillator**
   - Période: 14
   - %K et %D

8. **Williams %R**
   - Période: 14

9. **CCI (Commodity Channel Index)**
   - Période: 20

### 2. Analyse Avancée

#### Volatilité et Régime
- Détection du régime de volatilité (faible, normale, élevée)
- Détection du squeeze de Bollinger (breakout imminent)

#### Analyse du Carnet d'Ordres
- Détection des murs d'ordres (support/résistance)
- Calcul du déséquilibre du carnet d'ordres
- Identification des zones de liquidité

#### Niveaux Clés
- Pivot Points (méthode classique)
- Supports et résistances techniques
- Niveaux psychologiques

#### Patterns de Chandeliers
- Doji
- Hammer / Hanging Man
- Bullish / Bearish Engulfing

#### Divergences
- Divergence haussière (prix baisse, RSI monte)
- Divergence baissière (prix monte, RSI baisse)

#### Price Action
- Détection de breakouts
- Détection de reversements

### 3. Calcul Stop Loss / Take Profit

Le système calcule automatiquement les niveaux SL/TP basés sur:

1. **Bollinger Bands** (bande inférieure/supérieure)
2. **Volume Profile** (VAL/VAH)
3. **EMA 50**
4. **Limites de risque**:
   - Stop Loss max: 3% de perte
   - Take Profit max: 10% de gain
5. **Frais Hyperliquid** (intégrés dans le calcul)

### 4. Génération de Signaux

Le système utilise un système de scoring:

- **Signaux d'achat**: +1 à +3 points selon la force
- **Signaux de vente**: +1 à +3 points selon la force
- **Signal final**: Basé sur la différence entre les scores

**Confiance du signal**:
- **Haute**: Différence ≥ 3 points
- **Moyenne**: Différence ≥ 2 points
- **Faible**: Différence < 2 points

## 🔄 Flux de Données

```
1. fetch_historical_candles()
   ↓
2. fetch_order_book()
   ↓
3. Calcul des indicateurs techniques
   ↓
4. Analyse avancée (volatilité, order book, patterns, etc.)
   ↓
5. Génération du signal (scoring)
   ↓
6. Calcul SL/TP
   ↓
7. Retour de l'analyse complète
```

## ⚙️ Configuration

Tous les paramètres sont centralisés dans `config.py`:

- **API**: Timeout, retries, URLs
- **Indicateurs**: Périodes, seuils
- **Risk Management**: SL/TP max, ratios
- **Serveur Web**: Port, intervalles de mise à jour

## 🚀 Optimisations

### Gestion des Erreurs
- Retry logic avec backoff exponentiel
- Timeouts configurables
- Logging structuré
- Gestion gracieuse des erreurs API

### Performance
- Session HTTP réutilisable
- Validation des données
- Clamping des valeurs (RSI entre 0-100)
- Calculs optimisés (correction de Bessel pour écart-type)

### Robustesse
- Validation des entrées
- Gestion des cas limites
- Fallback sur valeurs par défaut
- Protection contre les divisions par zéro

## 📊 Format de Sortie

L'analyse retourne un dictionnaire avec:

```python
{
    'timestamp': '2024-01-01T12:00:00',
    'coin': 'BTC',
    'interval': '5m',
    'current_price': 50000.0,
    'signal': 'ACHAT',  # ou 'VENTE' ou 'NEUTRE'
    'signal_details': {
        'strength': 0.75,
        'buy_signals': 5,
        'sell_signals': 2,
        'reasons': [...],
        'scalping_signals': [...],
        'confidence': 'high'
    },
    'sl_tp': {
        'stop_loss': 48500.0,
        'take_profit': 52000.0,
        'stop_loss_percent': 3.0,
        'take_profit_percent': 4.0,
        'risk_reward': 1.33,
        'fees': {...},
        'total_fees_percent': 0.2,
        'net_gain_percent': 3.8,
        'break_even': 50100.0
    },
    'indicators': {...},
    'advanced_analysis': {...},
    'candles': [...]
}
```

## 🔐 Sécurité

- Pas de stockage de clés API (lecture seule)
- Validation des entrées utilisateur
- Timeouts pour éviter les blocages
- Gestion des erreurs sans exposer d'informations sensibles

## 📈 Améliorations Futures

- [ ] Backtesting automatique
- [ ] Alertes (email, Telegram, Discord)
- [ ] Support multi-coins simultané
- [ ] WebSocket pour données temps réel
- [ ] Base de données pour historique
- [ ] API REST pour intégration externe
- [ ] Machine Learning pour optimisation des paramètres

## 🐛 Dépannage

### Problèmes Courants

1. **Pas de données**
   - Vérifier la connexion Internet
   - Vérifier que l'API Hyperliquid est accessible
   - Augmenter le timeout dans `config.py`

2. **Erreurs de calcul**
   - Vérifier qu'il y a assez de chandeliers (minimum 50)
   - Vérifier les logs pour plus de détails

3. **Signaux toujours NEUTRE**
   - Ajuster les seuils dans `config.py`
   - Vérifier que les indicateurs sont calculés correctement

## 📝 Notes Techniques

- Le système utilise des calculs en virgule flottante (float)
- Les timestamps sont en secondes Unix
- Les prix sont en USD
- Les pourcentages sont en format décimal (0.03 = 3%)

## 🤝 Contribution

Pour améliorer le système:

1. Respecter la structure existante
2. Ajouter des tests pour les nouvelles fonctionnalités
3. Documenter les nouvelles méthodes
4. Mettre à jour `config.py` si nécessaire
5. Mettre à jour cette documentation

---

**Version**: 1.0  
**Dernière mise à jour**: 2024  
**Auteur**: Système de Trading Hyperliquid

