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

## Partenaires de l’écosystème (page d’accueil)

La migration `appstage/0028_partner` crée le catalogue des logos de la section
« Notre écosystème — Ils avancent avec Totinda ». L’appliquer via la procédure
de migration habituelle lors d’une livraison autorisée, avant d’utiliser cette
rubrique dans l’admin. Aucune donnée partenaire n’est préchargée.

Dans Django admin, ouvrir **Partenaires de l’écosystème** puis **Ajouter** :
nom du partenaire (également texte alternatif), logo image obligatoire (5 Mo
maximum), ordre d’affichage (les plus petits en premier), et case **Afficher
sur le site**. Les permissions Django d’ajout, modification, consultation et
suppression s’appliquent. Décocher la case masque un logo sans supprimer sa fiche;
supprimer une fiche la retire de la liste publique. Comme pour les ImageField
Django standards, cette suppression ne purge pas physiquement l’ancien fichier
du stockage; sa rétention/purge relève de l’exploitation.

L’API publique `GET /api/partners/` expose uniquement `id`, `name`, `image` des
partenaires actifs, triés par ordre puis identifiant, sans pagination; elle ne
permet aucune écriture. Le frontend actualise la liste au chargement, au retour
sur l’onglet et toutes les 60 secondes tant que la page reste visible. Si aucun
partenaire actif n’est disponible ou si la lecture échoue, la section est masquée.
Les anciens logos fixes doivent être ajoutés dans l’admin si leur affichage est
souhaité. Le stockage média configuré doit servir les images aux visiteurs.
