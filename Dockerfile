From python:3.11-slim

# Variables d'environnement
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# RUN apt-get update && apt-get install -y \
#     libpq-dev gcc cron \
#     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copie des fichiers de l'application
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
#CMD [ "gunicorn", "--bind", "0.0.0.0:8000", "project.wsgi:application" ]
# Ajouter script de démarrage
# COPY .start.sh /start.sh
# RUN chmod +x /start.sh

CMD ["gunicorn", "project.wsgi:application", "--bind", "0.0.0.0:8000"]