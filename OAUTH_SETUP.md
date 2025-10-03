# Configuration OAuth Google Drive

## Étapes de configuration

### 1. Google Cloud Console
1. Aller sur https://console.cloud.google.com/
2. Sélectionner votre projet ou en créer un nouveau
3. Activer l'API Google Drive : https://console.cloud.google.com/apis/library/drive.googleapis.com

### 2. Créer les credentials OAuth
1. Aller dans "APIs & Services" > "Credentials"
2. Cliquer "Create Credentials" > "OAuth client ID"
3. Type : "Web application"
4. Nom : "Demande Matériel LFM"
5. Authorized redirect URIs : 
   - http://localhost:5000/oauth/callback
   - http://127.0.0.1:5000/oauth/callback

### 3. Configurer l'écran de consentement
1. Aller dans "OAuth consent screen"
2. Type d'utilisateur : "External" (ou "Internal" si Google Workspace)
3. Remplir les informations :
   - App name: "Demande de Matériel LFM"
   - User support email: [votre email]
   - Developer contact email: [votre email]

### 4. Ajouter les scopes
- https://www.googleapis.com/auth/drive.file

### 5. Ajouter des utilisateurs de test (Mode Test)
Ajouter les emails des enseignants qui utiliseront l'application.

## Mode Test vs Production

### Mode Test (Recommandé pour commencer)
- Jusqu'à 100 utilisateurs
- Pas de vérification Google nécessaire
- Parfait pour une école
- Warning screen pour les utilisateurs

### Mode Production
- Utilisateurs illimités
- Vérification Google obligatoire
- Nécessite politique de confidentialité
- Processus de révision 1-6 semaines

## Télécharger credentials.json
1. Dans Google Cloud Console > Credentials
2. Cliquer sur votre OAuth client ID
3. Télécharger le JSON
4. Renommer en "credentials.json"
5. Placer dans le dossier de l'application

## URLs importantes
- Google Cloud Console: https://console.cloud.google.com/
- OAuth Consent Screen: https://console.cloud.google.com/apis/credentials/consent
- API Library: https://console.cloud.google.com/apis/library
- Credentials: https://console.cloud.google.com/apis/credentials