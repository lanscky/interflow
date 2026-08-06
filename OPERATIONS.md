# Exploitation de Totinda Backend

## Secrets requis

Copier `.env.example` vers `.env`, puis fournir des valeurs uniques via le gestionnaire de secrets de production. Ne jamais réutiliser les anciennes valeurs présentes dans l'historique Git.

À chaque exposition suspectée, révoquer puis remplacer immédiatement : `SECRET_KEY`, les mots de passe MySQL/SMTP, les clés AWS, PayPal et Stripe, `FLOWER_BASIC_AUTH` et `NEXTAUTH_SECRET` côté frontend. Une rotation de `SECRET_KEY` invalide les sessions et jetons signés existants.

## Déploiement

```sh
docker compose build
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py collectstatic --noinput
docker compose up -d
```

Les interfaces d'exploitation ne sont pas publiques. Elles sont activées explicitement et liées à localhost :

```sh
docker compose --profile tools up -d phpmyadmin flower
```

## Vérifications

```sh
env/bin/python manage.py test --settings=project.settings_test
env/bin/python manage.py check --deploy
docker compose config --quiet
```

## Sauvegarde et restauration MySQL

Stocker les sauvegardes chiffrées dans un espace privé avec une politique de rétention ; aucun dump ne doit être ajouté au dépôt.

```sh
docker compose exec -T db mysqldump -u root -p totinda > /chemin/prive/totinda.sql
docker compose exec -T db mysql -u root -p totinda < /chemin/prive/totinda.sql
```

Tester régulièrement la restauration sur une base isolée avant de considérer une sauvegarde comme valide.
