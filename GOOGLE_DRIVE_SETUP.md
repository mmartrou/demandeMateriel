# Configuration Google Drive pour l'upload d'images

## 📋 Étapes de configuration

### 1. **Créer un compte de service Google** (Recommandé)

Si vous n'avez pas accès à Google Cloud Console, vous pouvez :

#### Option A : Demander à quelqu'un avec accès
1. Aller sur [Google Cloud Console](https://console.cloud.google.com/)
2. Créer un nouveau projet ou sélectionner un existant
3. Activer l'API Google Drive
4. Créer un compte de service :
   - IAM et administration → Comptes de service → Créer un compte de service
   - Télécharger le fichier JSON des credentials
5. Partager votre dossier Google Drive avec l'email du compte de service

#### Option B : Utiliser vos credentials personnels
1. Créer une application OAuth dans Google Cloud Console
2. Télécharger le fichier `credentials.json`
3. La première fois, vous devrez autoriser l'application dans votre navigateur

### 2. **Configuration des fichiers**

1. **Renommez** `credentials_example.json` en `credentials.json`
2. **Remplacez** le contenu par vos vrais credentials Google
3. **Modifiez** `config_google.py` :
   ```python
   # ID du dossier Google Drive où stocker les images
   GOOGLE_FOLDER_ID = "1ABC123456DEF"  # Remplacez par l'ID de votre dossier
   ```

### 3. **Obtenir l'ID du dossier Google Drive**

1. Allez dans votre dossier Google Drive
2. L'URL ressemble à : `https://drive.google.com/drive/folders/1ABC123456DEF`
3. L'ID du dossier est : `1ABC123456DEF`

### 4. **Test de fonctionnement**

Une fois configuré :
- ✅ L'upload d'images sera automatique vers Google Drive
- ✅ Les images seront publiques et visibles dans l'application
- ✅ Fallback vers stockage local si Google Drive indisponible

## 🔧 Dépannage

### Erreur "credentials.json manquant"
- Assurez-vous que le fichier `credentials.json` existe
- Vérifiez que le contenu est un JSON valide

### Erreur d'autorisation Google
- Supprimez le fichier `token.json` et relancez
- Autorisez l'application dans votre navigateur

### Images non visibles
- Vérifiez que `GOOGLE_FOLDER_ID` est correct
- Assurez-vous que le dossier est partagé publiquement

## 💡 Mode développement sans Google Drive

Si vous ne pouvez pas configurer Google Drive maintenant :
- L'application fonctionne avec stockage local
- Les images sont sauvées dans `static/uploads/`
- Configurez Google Drive plus tard quand possible