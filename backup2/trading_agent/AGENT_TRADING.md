# 🤖 Agent de Trading Automatisé Hyperliquid

## 📋 Vue d'ensemble

L'agent de trading automatisé se connecte aux signaux générés par le système d'analyse et exécute automatiquement les trades sur Hyperliquid.

## 🔐 Configuration des Clés API

### Méthode 1 : Variables d'environnement (Recommandé)

```bash
# Windows PowerShell
$env:HYPERLIQUID_PRIVATE_KEY="votre_cle_privee_ici"

# Windows CMD
set HYPERLIQUID_PRIVATE_KEY=votre_cle_privee_ici

# Linux/Mac
export HYPERLIQUID_PRIVATE_KEY="votre_cle_privee_ici"
```

### Méthode 2 : Fichier config.py

Éditez `config.py` et remplissez :

```python
HYPERLIQUID_API = {
    'wallet_address': 'votre_adresse_wallet',
    'private_key': 'votre_cle_privee',  # ⚠️ Attention : moins sécurisé
    'use_referral': True,  # Si vous avez un code parrainage
    'referral_code': 'VOTRE_CODE',
    'staking_tier': 'bronze',  # wood, bronze, silver, gold, platinum, diamond
    'volume_30d': 0.0,  # Volume 30 jours pour calcul frais
}
```

## 🚀 Utilisation

### Lancement de base

```bash
python hyperliquid_trading_agent.py
```

### Options disponibles

```bash
python hyperliquid_trading_agent.py --help
```

**Options principales :**

- `--coin BTC` : Crypto à trader (défaut: BTC)
- `--interval 5m` : Intervalle de temps (défaut: 5m)
- `--check-interval 60` : Intervalle de vérification en secondes (défaut: 60)
- `--max-position 1000` : Taille max position en USD (défaut: 1000)
- `--min-confidence medium` : Confiance minimum (high/medium/low, défaut: medium)

### Exemples

**Trading BTC avec vérification toutes les 30 secondes :**
```bash
python hyperliquid_trading_agent.py --coin BTC --interval 5m --check-interval 30
```

**Trading ETH avec positions max de 500 USD :**
```bash
python hyperliquid_trading_agent.py --coin ETH --max-position 500
```

**Trading avec confiance haute uniquement :**
```bash
python hyperliquid_trading_agent.py --min-confidence high
```

## ⚙️ Fonctionnalités

### 1. Gestion Automatique des Positions

- **Ouverture** : Ouvre automatiquement des positions basées sur les signaux
- **Stop Loss** : Place automatiquement un SL basé sur l'analyse
- **Take Profit** : Place automatiquement un TP basé sur l'analyse
- **Fermeture** : Gère la fermeture des positions

### 2. Gestion des Risques

- **Taille de position** : Calculée selon la force du signal et la confiance
- **Limite quotidienne** : Maximum 50 trades par jour (configurable)
- **Solde minimum** : Vérifie le solde avant chaque trade
- **Slippage max** : 0.1% par défaut

### 3. Calcul Intelligent de la Taille

La taille de position est calculée selon :

- **Force du signal** (0-1) :
  - > 0.8 : 100% de la taille max
  - > 0.6 : 75%
  - > 0.4 : 50%
  - < 0.4 : 25%

- **Confiance** :
  - `high` : 100%
  - `medium` : 75%
  - `low` : 50%

- **Limite** : Maximum 10% du solde total

### 4. Frais Optimisés

L'agent utilise les frais réels Hyperliquid :
- **Maker** : 0.01% (0.0001)
- **Taker** : 0.035% (0.00035)

Avec réductions possibles :
- **Parrainage** : -4%
- **Staking HYPE** : -5% à -40% selon le tier

## 📊 Monitoring

L'agent affiche en temps réel :

- Signal actuel (ACHAT/VENTE/NEUTRE)
- Prix actuel
- Confiance du signal
- Solde disponible
- Positions ouvertes
- Historique des trades

## 📝 Logs

Les logs sont sauvegardés dans :
- **Fichier** : `trading_agent.log`
- **Console** : Affichage en temps réel

## ⚠️ Sécurité

### Bonnes Pratiques

1. **Ne jamais commiter les clés privées** dans Git
2. **Utiliser les variables d'environnement** de préférence
3. **Tester d'abord avec de petites positions**
4. **Surveiller les logs** régulièrement
5. **Vérifier les permissions** du fichier config.py

### Protection des Clés

```bash
# Windows : Restreindre l'accès au fichier
icacls config.py /deny Users:R

# Linux/Mac
chmod 600 config.py
```

## 🔧 Configuration Avancée

### Modifier les limites dans le code

Dans `hyperliquid_trading_agent.py` :

```python
self.max_position_size = 1000.0  # USD
self.max_daily_trades = 50
self.max_slippage = 0.001  # 0.1%
self.min_confidence = 'medium'
```

### Désactiver le trading automatique

Pour tester sans trader réellement, commentez la ligne dans `execute_trade()` :

```python
# order_result = self.place_order(...)
order_result = {'status': 'skipped', 'reason': 'Mode test'}
```

## 📈 Statistiques

Pour voir les statistiques de trading :

```python
from hyperliquid_trading_agent import HyperliquidTradingAgent

agent = HyperliquidTradingAgent()
stats = agent.get_trade_statistics()
print(stats)
```

## 🐛 Dépannage

### Erreur : "Wallet address et private key requis"

**Solution** : Configurez les clés API (voir section Configuration)

### Erreur : "Solde insuffisant"

**Solution** : 
- Vérifiez votre solde sur Hyperliquid
- Réduisez `max_position_size`
- Vérifiez que vous avez assez de marge

### Erreur : "Limite quotidienne atteinte"

**Solution** : 
- Attendez le lendemain
- Augmentez `max_daily_trades` dans le code

### Erreur de signature

**Solution** :
- Vérifiez que la clé privée correspond au wallet
- Vérifiez le format de la clé privée (doit commencer par 0x)

## 📚 API Hyperliquid

L'agent utilise l'API officielle Hyperliquid :
- **Info API** : `https://api.hyperliquid.xyz/info`
- **Exchange API** : `https://api.hyperliquid.xyz/exchange`

Documentation : https://hyperliquid.gitbook.io/hyperliquid-docs/

## ⚡ Performance

- **Latence** : < 100ms pour placement d'ordre
- **Vérification** : Configurable (défaut: 60s)
- **Mémoire** : ~50MB
- **CPU** : Minimal (vérification périodique)

## 🔄 Workflow

```
1. Agent démarre
   ↓
2. Récupère signaux toutes les X secondes
   ↓
3. Analyse le signal (force, confiance, SL/TP)
   ↓
4. Vérifie les conditions (solde, limites, positions)
   ↓
5. Calcule la taille de position
   ↓
6. Place l'ordre Market
   ↓
7. Place les ordres SL/TP
   ↓
8. Enregistre le trade
   ↓
9. Retour à l'étape 2
```

## 🎯 Prochaines Améliorations

- [ ] Support des ordres limites
- [ ] Trailing stop loss
- [ ] Gestion multi-coins
- [ ] Backtesting intégré
- [ ] Interface web pour monitoring
- [ ] Alertes Telegram/Discord
- [ ] Stratégies personnalisables

---

**⚠️ AVERTISSEMENT** : Le trading automatisé comporte des risques. Testez toujours avec de petites positions avant d'augmenter. L'auteur n'est pas responsable des pertes.

**Version** : 1.0  
**Dernière mise à jour** : 2024

