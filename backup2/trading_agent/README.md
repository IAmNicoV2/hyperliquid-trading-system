# 🤖 Agent de Trading Automatisé Hyperliquid

Ce dossier contient tous les fichiers nécessaires pour l'agent de trading automatisé.

## 📁 Structure

```
trading_agent/
├── hyperliquid_trading_agent.py  # Agent principal
├── AGENT_TRADING.md              # Documentation complète
├── .env.example                  # Template de configuration
├── __init__.py                   # Module Python
└── README.md                     # Ce fichier
```

## 🚀 Utilisation

### 1. Configuration

Copiez `.env.example` en `.env` et remplissez vos clés API :

```bash
copy .env.example .env
```

Ou configurez dans `config.py` à la racine du projet.

### 2. Installation des dépendances

Depuis la racine du projet (`C:\Users\user\Agents`) :

```bash
pip install -r requirements.txt
```

### 3. Lancement

Depuis la racine du projet :

```bash
python trading_agent\hyperliquid_trading_agent.py
```

Ou depuis ce dossier :

```bash
cd trading_agent
python hyperliquid_trading_agent.py
```

## 📚 Documentation

Consultez `AGENT_TRADING.md` pour la documentation complète.

## ⚠️ Sécurité

- Ne commitez JAMAIS le fichier `.env` dans Git
- Utilisez les variables d'environnement de préférence
- Testez toujours avec de petites positions d'abord

## 🔗 Liens

- Documentation Hyperliquid : https://hyperliquid.gitbook.io/hyperliquid-docs/
- Système de signaux : `../hyperliquid_signals.py`
- Configuration : `../config.py`

