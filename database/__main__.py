"""python -m database : crée les tables et applique les migrations."""
from database import init_database

init_database()
print("Database initialized successfully!")
