# Configuration PostgreSQL Railway - Variables séparées

## 🎯 Problème résolu
L'URL PostgreSQL complète (`DATABASE_URL`) contient des caractères d'encodage invalides sur Railway.  
Les **variables séparées** évitent ce problème et sont plus fiables.

## 📝 Variables à configurer sur Railway

### Dans Railway Dashboard → Variables :

```bash
# Variables PostgreSQL (recommandées)
PGHOST=postgres.railway.internal
PGPORT=5432  
PGUSER=postgres
PGPASSWORD=VotrMotDePassePostgreSQL
PGDATABASE=railway

# Variables Flask
FLASK_ENV=production
PORT=8080
```

## 🔧 Comment configurer :

### 1. **Supprimer l'ancienne variable (optionnel)** :
- Supprimer `DATABASE_URL` si elle cause des problèmes d'encodage

### 2. **Ajouter les nouvelles variables** :
Dans Railway Dashboard → **Variables** → **+ New Variable** :

| Nom | Valeur | Description |
|-----|--------|-------------|
| `PGHOST` | `postgres.railway.internal` | Adresse du serveur PostgreSQL |
| `PGPORT` | `5432` | Port PostgreSQL |
| `PGUSER` | `postgres` | Nom d'utilisateur |
| `PGPASSWORD` | `[Votre mot de passe]` | Mot de passe PostgreSQL |
| `PGDATABASE` | `railway` | Nom de la base de données |
| `FLASK_ENV` | `production` | Mode Flask |
| `PORT` | `8080` | Port de l'application |

### 3. **Obtenir les vraies valeurs** :
- Dans Railway : **PostgreSQL service** → **Variables** tab
- Copier les valeurs de `PGHOST`, `PGPASSWORD`, etc.

## ⚡ Priorité de connexion :

1. **✅ Variables séparées** (`PGHOST`, `PGUSER`, etc.) - Plus fiable
2. **🔄 URL complète** (`DATABASE_URL`) - Fallback 
3. **🗄️ SQLite local** - Si PostgreSQL échoue

## 🎉 Avantages :

- ✅ **Pas de problèmes d'encodage UTF-8**
- ✅ **Plus facile à déboguer**
- ✅ **Compatibilité garantie**
- ✅ **Fallback SQLite automatique**

## 🧪 Test :

Après configuration, les logs montreront :
```
INFO:database:Connexion PostgreSQL avec variables séparées: postgres.railway.internal:5432
INFO:database:✅ Connexion PostgreSQL (variables séparées) réussie
```

Au lieu de :
```
ERROR:database:Erreur PostgreSQL: 'utf-8' codec can't decode byte 0xf4
INFO:database:Utilisation de SQLite
```