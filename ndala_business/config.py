import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'cle_secrete_facile_a_changer'
    # Utilisation de SQLite par défaut pour le développement
    DATABASE = 'database.db'
