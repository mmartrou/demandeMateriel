# Demande Matériel

Site permettant une demande facilitée du matériel de laboratoire.

## Fonctionnalités

- 🧪 **Interface intuitive** : Formulaire simple pour créer des demandes de matériel
- 👨‍🏫 **Gestion des enseignants** : Liste déroulante des enseignants disponibles
- 📅 **Planification** : Sélection de date pour chaque demande
- 🎓 **Organisation par classe** : Association des demandes aux classes
- 📋 **Visualisation** : Interface de consultation de toutes les demandes avec filtres
- 🗓️ **Calendrier** : Vue calendaire des demandes planifiées
- 📊 **Export CSV** : Exportation des données pour traitement externe avec Python
- 📱 **Responsive** : Interface adaptée aux mobiles et tablettes

## 🚀 Déploiement rapide (Recommandé)

### Option 1 : GitHub Codespaces (Le plus simple)
1. Sur GitHub, cliquer sur "Code" → "Codespaces" → "Create codespace"
2. Attendre le chargement automatique
3. L'application s'ouvre automatiquement dans votre navigateur
4. **Avantage** : Aucune installation, accessible partout, partageable

### Option 2 : Railway.app (Hébergement permanent gratuit)
1. Aller sur [Railway.app](https://railway.app)
2. Se connecter avec GitHub
3. Sélectionner ce repository
4. Déploiement automatique → URL publique générée

### Option 3 : PythonAnywhere (Gratuit)
1. Compte gratuit sur [PythonAnywhere](https://www.pythonanywhere.com)
2. Uploader les fichiers
3. Créer une Web App Flask

## 💻 Installation locale

1. Cloner le repository :
```bash
git clone https://github.com/mmartrou/demandeMateriel.git
cd demandeMateriel
```

2. Installer les dépendances Python :
```bash
pip install -r requirements.txt
```

3. Initialiser la base de données :
```bash
python database.py
```

4. Lancer l'application :
```bash
python app.py
```

L'application sera accessible sur `http://localhost:5000`

> 📖 **Guide détaillé** : Voir [DEPLOYMENT.md](DEPLOYMENT.md) pour toutes les options

## Utilisation

### Créer une demande
1. Aller sur la page d'accueil
2. Sélectionner un enseignant dans la liste déroulante
3. Choisir la date de la demande
4. Renseigner le nom de la classe
5. Décrire le matériel nécessaire
6. Indiquer la quantité et d'éventuelles notes
7. Cliquer sur "Envoyer la demande"

### Consulter les demandes
- **Vue liste** : Aller sur "Voir les Demandes" pour une vue tabulaire avec filtres
- **Vue calendrier** : Aller sur "Calendrier" pour une vue mensuelle
- **Export CSV** : Utiliser le bouton "Export CSV" pour télécharger les données

### Filtrage
- Filtrer par enseignant
- Filtrer par période (date de début/fin)
- Visualiser les détails de chaque demande

## Structure du projet

```
demandeMateriel/
├── app.py                 # Application Flask principale
├── database.py           # Configuration et modèles de base de données
├── requirements.txt      # Dépendances Python
├── templates/           # Templates HTML
│   ├── base.html        # Template de base
│   ├── index.html       # Formulaire de demande
│   ├── requests.html    # Vue liste des demandes
│   └── calendar.html    # Vue calendrier
├── static/             # Fichiers statiques
│   ├── css/           # Feuilles de style
│   └── js/            # Scripts JavaScript
└── README.md          # Documentation
```

## Technologies utilisées

- **Backend** : Python Flask
- **Base de données** : SQLite
- **Frontend** : HTML5, CSS3, JavaScript (vanilla)
- **UI** : Bootstrap-like styling (autonome, sans CDN)
- **Calendrier** : Implémentation JavaScript personnalisée

## API

### Endpoints disponibles

- `GET /` - Page d'accueil avec formulaire
- `GET /requests` - Vue liste des demandes
- `GET /calendar` - Vue calendrier
- `GET /api/requests` - API pour récupérer les demandes (JSON)
- `POST /api/requests` - API pour créer une demande
- `GET /api/calendar-events` - API pour les événements du calendrier
- `GET /export/csv` - Export des demandes en CSV

### Format des données

Les demandes contiennent :
- ID unique
- Enseignant (nom et email)
- Date de la demande
- Nom de la classe
- Description du matériel
- Quantité
- Notes optionnelles
- Date de création

## Contribution

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/nouvelle-fonctionnalite`)
3. Commit les changements (`git commit -am 'Ajout nouvelle fonctionnalité'`)
4. Push sur la branche (`git push origin feature/nouvelle-fonctionnalite`)
5. Créer une Pull Request

## Licence

Ce projet est sous licence MIT.
