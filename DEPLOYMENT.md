# Guide de Déploiement

## 🚀 Déploiement sur Railway (Gratuit - Recommandé)

1. Créer un compte sur [Railway.app](https://railway.app)
2. Connecter votre repository GitHub
3. Railway détecte automatiquement Flask
4. L'app est accessible via une URL publique

## 🌐 Déploiement sur Heroku

1. Créer un `Procfile` :
```
web: python app.py
```

2. Modifier `app.py` pour Heroku :
```python
import os
# À la fin du fichier
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
```

## 📱 Déploiement sur PythonAnywhere (Gratuit)

1. Créer un compte gratuit sur PythonAnywhere
2. Uploader les fichiers
3. Configurer une Web App Flask
4. URL accessible : `https://votrenom.pythonanywhere.com`

## 🏠 GitHub Codespaces (Pour tests rapides)

1. Cliquer sur "Code" → "Codespaces" → "Create codespace"
2. L'environnement se lance automatiquement
3. L'app est accessible via l'URL générée
4. Parfait pour des démonstrations rapides

## ⚡ Déploiement sur Render (Gratuit)

1. Créer un compte sur [Render.com](https://render.com)
2. Connecter GitHub
3. Déploiement automatique à chaque commit