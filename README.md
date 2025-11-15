# 🚀 Système de Trading Hyperliquid

Système complet de génération de signaux de trading et agent automatisé pour Hyperliquid.

## 📋 Fonctionnalités

### 🎯 Générateur de Signaux
- **Indicateurs techniques avancés** : RSI, MACD, EMA, Bollinger Bands, ATR, Stochastic, Williams %R, CCI
- **Détection professionnelle supports/résistances** : Swing Highs/Lows, Volume Profile, Touches multiples, Zones de consolidation
- **Pivot Points multiples** : Classique, Fibonacci, Camarilla
- **Analyse avancée** : Volatilité, Order Book, Patterns de chandeliers, Divergences
- **Calcul SL/TP optimisé** : Intègre les frais Hyperliquid réels avec réductions

### 🤖 Agent de Trading Automatisé
- Exécution automatique des trades basés sur les signaux
- Gestion des risques (taille de position, limites quotidiennes)
- Placement automatique de Stop Loss et Take Profit
- Monitoring en temps réel

### 🌐 Interface Web
- Dashboard en temps réel
- Graphique des prix interactif
- Affichage des signaux avec SL/TP
- Historique des signaux
- Indicateurs techniques en direct

## 🚀 Installation

```bash
pip install -r requirements.txt
```

## 📖 Utilisation

### Serveur Web (Recommandé)
```bash
python hyperliquid_web_server.py
```
Puis ouvrez http://localhost:5000

### Agent de Trading
```bash
cd trading_agent
python hyperliquid_trading_agent.py
```

### Générateur de Signaux (CLI)
```bash
python hyperliquid_signals.py
```

## ⚙️ Configuration

1. Copiez `.env.example` en `.env` dans `trading_agent/`
2. Configurez vos clés API dans `.env` ou variables d'environnement
3. Ajustez les paramètres dans `config.py` si nécessaire

## 📚 Documentation

- **Guide de démarrage** : `DEMARRAGE_RAPIDE.md`
- **Documentation technique** : `README_TECHNIQUE.md`
- **Agent de trading** : `trading_agent/AGENT_TRADING.md`
- **Améliorations** : `AMELIORATIONS.md`
- **Supports/Résistances** : `AMELIORATIONS_SUPPORTS_RESISTANCES.md`

## 🔐 Sécurité

⚠️ **IMPORTANT** : Ne commitez JAMAIS vos clés API dans Git. Utilisez les variables d'environnement ou le fichier `.env` (non versionné).

## 📊 Frais Hyperliquid

Le système utilise les frais réels Hyperliquid :
- **Maker** : 0.01%
- **Taker** : 0.035% (niveau 0)
- **Tiers de volume** : 6 niveaux selon volume 14 jours
- **Réductions** : Parrainage (-4%) + Staking HYPE (-5% à -40%)

## 🛠️ Technologies

- Python 3.8+
- Flask (Interface web)
- Requests (API Hyperliquid)
- eth-account (Signatures pour trading)

## 📝 License

Voir le fichier LICENSE pour plus d'informations.

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou une pull request.

---

**Version** : 2.0  
**Dernière mise à jour** : 2024

