# 🚀 Guide de Démarrage Rapide

## Installation

```bash
pip install -r requirements.txt
```

## Utilisation

### 1. Interface Web (Recommandé)

Lancez le serveur web pour accéder à l'interface graphique :

```bash
python hyperliquid_web_server.py
```

Puis ouvrez votre navigateur à l'adresse : **http://localhost:5000**

**Fonctionnalités de l'interface web :**
- ✅ Monitoring en temps réel
- ✅ Graphique des prix en direct
- ✅ Affichage des signaux avec SL/TP
- ✅ Historique des signaux
- ✅ Indicateurs techniques en temps réel
- ✅ Calcul automatique de Stop Loss et Take Profit

### 2. Mode Ligne de Commande

Pour une analyse unique :
```bash
python hyperliquid_signals.py
```

Pour le monitoring continu :
```bash
python hyperliquid_signals.py --monitor
```

## Fonctionnalités Ajoutées

### ✨ Stop Loss & Take Profit

Le système calcule automatiquement :
- **Stop Loss** basé sur :
  - Bollinger Bands (bande inférieure/supérieure)
  - Volume Profile (VAL/VAH)
  - EMA 50
  - Maximum 3% de perte

- **Take Profit** basé sur :
  - Milieu des Bollinger Bands
  - Bande supérieure/inférieure BB
  - Volume Profile VAH/VAL
  - Maximum 10% de gain

- **Risk/Reward Ratio** : Calculé automatiquement

### 📊 Interface Web

- Dashboard en temps réel
- Graphique interactif des prix
- Historique des signaux
- Mise à jour automatique toutes les 5 secondes
- Design moderne et responsive

### 🔔 Alertes Visuelles

- Badges colorés pour les signaux (vert=ACHAT, rouge=VENTE, gris=NEUTRE)
- Animation pulsante quand le monitoring est actif
- Indicateurs en temps réel

## Configuration

### Configuration Rapide

Tous les paramètres sont maintenant centralisés dans `config.py` :

- `DEFAULT_COIN = "BTC"` → Changer la crypto par défaut
- `DEFAULT_INTERVAL = "5m"` → Changer l'intervalle par défaut
- `WEB_SERVER_PORT = 5000` → Changer le port du serveur
- `API_TIMEOUT = 10` → Timeout des requêtes API (secondes)
- `MAX_RETRIES = 3` → Nombre de tentatives en cas d'erreur

### Configuration Avancée

Dans `config.py`, vous pouvez également modifier :
- Périodes des indicateurs techniques (RSI, MACD, EMA, etc.)
- Seuils de signaux (RSI_OVERSOLD, RSI_OVERBOUGHT, etc.)
- Limites de risque (MAX_STOP_LOSS_PERCENT, MAX_TAKE_PROFIT_PERCENT)
- Intervalles de mise à jour (WEB_UPDATE_INTERVAL, MONITORING_INTERVAL)

## Exemples d'Utilisation

### Scalping 1 minute
```python
# Dans hyperliquid_web_server.py, ligne ~470
init_generator(coin="BTC", interval="1m")
```

### Swing Trading 15 minutes
```python
init_generator(coin="BTC", interval="15m")
```

### Analyser ETH
```python
init_generator(coin="ETH", interval="5m")
```

## Dépannage

**Le serveur ne démarre pas ?**
- Vérifiez que Flask est installé : `pip install flask flask-cors`
- Vérifiez que le port 5000 n'est pas utilisé

**Pas de données ?**
- Vérifiez votre connexion Internet
- Vérifiez que l'API Hyperliquid est accessible

**Erreur d'encodage ?**
- Le script configure automatiquement UTF-8 pour Windows
- Si problème persiste, utilisez Python 3.8+

## Documentation

- **Guide de démarrage rapide**: `DEMARRAGE_RAPIDE.md` (ce fichier)
- **Documentation technique**: `README_TECHNIQUE.md`
- **Améliorations récentes**: `AMELIORATIONS.md`
- **Configuration**: `config.py` (fichier de configuration)

## Support

Pour toute question technique, consultez le `README_TECHNIQUE.md`

---

**Bon trading ! 📈📉**

