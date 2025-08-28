#!/bin/bash
set -e

echo "Déploiement en cours..."

cd /var/www/interflow
# Pull du dernier code
git reset --hard
git pull origin main

# Build et redémarrage des conteneurs
docker-compose down
docker-compose build --no-cache
docker-compose up -d

echo "Déploiement terminé."
