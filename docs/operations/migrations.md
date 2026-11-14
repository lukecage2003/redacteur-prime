# Migrations de base de données

- Toutes les migrations sont versionnées (`db/migrations/versions/`), écrites et relues à la main.
- **Additives d'abord** : ajouter colonne/table → déployer le code → migrer les données → retirer
  l'ancien en migration séparée, plus tard.
- `downgrade` toujours écrit et testé en CI (aller-retour). En production, on ne descend pas :
  on corrige par une nouvelle migration.
- Opération destructive (DROP, suppression de données, changement de type avec perte) :
  ADR + sauvegarde vérifiée + accord explicite du propriétaire.
- Déploiement : le Cloud Run Job `primestone-migrate` exécute `alembic upgrade head` avant le
  déploiement des services (migration compatible avec la version précédente du code).
