# Configuration GitHub (à faire par le propriétaire)

0. **Constat du 2026-11-14** : le dépôt est **public** et sa branche par défaut est encore
   `claude/sweet-feynman-b9933b` (première branche poussée). La PR #3 a été fusionnée dans `main`.
1. **Branche par défaut** : `main` (Settings → General → Default branch → `main`).
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
