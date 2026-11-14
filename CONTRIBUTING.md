# CONTRIBUTING

## Branches

| Branche | Usage |
|---|---|
| `main` | stable, protégée, uniquement via PR |
| `feature/<sujet>` | nouvelle fonctionnalité |
| `fix/<sujet>` | correction |
| `release/<version>` | préparation de version |

Pas de branche `develop` (développement trunk-based, ADR-0008). Fusion par « squash merge ».
Jamais de push direct ni de force push sur `main`.

## Commits

Format conventionnel : `type(portée): description` — types `feat`, `fix`, `docs`, `test`,
`refactor`, `chore`, `ci`, `perf`. Exemple : `feat(library): import par lots avec reprise`.

## Pull Requests

- Une PR par fonctionnalité importante, petite et cohérente.
- Remplir le modèle (`.github/pull_request_template.md`) : objectif, changements, fichiers,
  architecture, tests et résultats, risques, limitations, procédure de vérification.
- La CI doit être verte. Aucune fusion automatique ; approbation humaine requise.

## Checks obligatoires (règles de protection)

À activer **après** un premier passage vert réel sur GitHub : `python`, `migrations`, `web`,
`docker`, `secrets`. Voir docs/operations/github-setup.md.

## Définition de « terminé »

Code + tests + documentation à jour (ROADMAP, DATA_MODEL, API, ADR si décision) + statut honnête
(IMPLEMENTED / TESTED / VALIDATED).
