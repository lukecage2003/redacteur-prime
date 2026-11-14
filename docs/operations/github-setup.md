# Configuration GitHub (à faire par le propriétaire)

1. **Branche par défaut** : `main`.
2. **Règles de protection de `main`** (Settings → Rules → Rulesets), après un premier passage
   vert réel de la CI :
   - PR obligatoire, 0 ou 1 approbation (projet personnel), résolution des conversations ;
   - checks obligatoires : `python`, `migrations`, `web`, `docker`, `secrets` ;
   - interdiction des force push et de la suppression ;
   - historique linéaire (squash).
3. **Environnements** : `staging` (déploiement depuis `main` uniquement), `production`
   (relecteur obligatoire = propriétaire ; sur un dépôt privé, nécessite une offre GitHub
   le permettant).
4. **Dependency review** : sur un dépôt public, définir la variable de dépôt
   `DEPENDENCY_REVIEW_ENABLED=true`.
5. **Sécurité** : activer Dependabot alerts et secret scanning si disponibles.
