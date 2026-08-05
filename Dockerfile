# Utiliser une image Python officielle légère
FROM python:3.10-slim

# Empêcher Python d'écrire des fichiers .pyc et forcer l'affichage immédiat des logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Installer les dépendances système requises pour MySQL (mysqlclient)
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Définir le dossier de travail dans le conteneur
WORKDIR /app

# Copier le fichier des dépendances et les installer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le reste du code de l'application
COPY . .

# Exposer le port 5000 (celui sur lequel Flask tourne)
EXPOSE 5000

# Commande de lancement de l'application
CMD ["python", "app.py"]