# CLAUDE.md — méthode de travail persistante

Ce fichier est lu au début de chaque session Claude Code. Il prime sur les habitudes
par défaut. En cas de doute, **vérifier le dépôt** : ne jamais supposer qu'un résultat
d'une session précédente est toujours valide.

## Vision

PRIMESTONE EDITORIAL 2.0 est une plateforme d'intelligence éditoriale pour les comics
(usage personnel, non commercial). Priorités, dans l'ordre : **exactitude documentaire**,
**traçabilité**, qualité éditoriale, puis vitesse.

Décisions produit fixes : autonomie DIRECTOR (L5 supervisé), analyse FORENSIC,
infrastructure CLOUD (GCP), voix ADAPTIVE, marchés FR + EN, storytelling MAXIMUM,
architecture indépendante des fournisseurs IA.

## Début de chaque mission

1. `git status`, `git log --oneline -15`, branches distantes.
2. Lire `ROADMAP.md` (statuts) et les ADR concernés dans `docs/adr/`.
3. Lancer `make check` (ou les commandes ci-dessous) pour constater l'état réel.
4. Annoncer le plan avant de modifier quoi que ce soit d'important.

## Commandes

```bash
uv sync && pnpm install                    # dépendances
docker compose up -d db                    # PostgreSQL 16 + pgvector
export PRIMESTONE_TEST_DATABASE_URL=postgresql+psycopg://primestone:primestone@localhost:5432/primestone_test
uv run pytest                              # tests Python (intégration incluse si la variable est définie)
uv run ruff check . && uv run ruff format --check .
uv run mypy                                # strict
uv run alembic upgrade head                # migrations (PRIMESTONE_DATABASE_URL)
uv run alembic revision -m "..."           # nouvelle migration (écrite à la main, relue)
pnpm --filter @primestone/web lint|typecheck|test|build
uv run primestone-library import DOSSIER --process        # bibliothèque (phase 2)
uv run primestone-vision estimate|analyze|show|benchmark-panels  # vision (phase 3), budget explicite
uv run primestone-forensic analyze|report|observations --documents ID…  # forensique (phase 4), gratuit
uv run primestone-knowledge build|entities|entity|graph|path|search|merge|alias|rename|retract  # phase 5
uv run primestone-editorial agents|dossier|audit|check|social|show|approve|reject  # phases 6, 9
uv run primestone-lab create|list|show|evidence|retract|alternative|research|review|ask  # phase 7
uv run primestone-market sources|add-source|verify|import|collect|snapshot|topic|analysis|brief  # phase 8
uv run primestone-script list|show|create|version|step|evaluate|review|validate|adapt  # phase 10
uv run primestone-audience segments|segment|evidence|link|collect|community|brief  # phase 15
uv run primestone-performance import|contents|link|report|review|authorize|sync|objective|objectives|experiment-*  # phases 11, 14
```

## Architecture (résumé — détails dans ARCHITECTURE.md)

- Monolithe modulaire en monorepo (ADR-0001). Cœur : `packages/primestone`.
- Une intelligence = un sous-paquet de `primestone`, avec des interfaces explicites.
- Tout appel à un modèle passe par `primestone.ai_gateway` (ADR-0005). Jamais d'appel direct
  à un SDK fournisseur depuis le code métier.
- Tâches asynchrones : `primestone.jobs.PostgresJobQueue` (ADR-0004). Toute étape est
  idempotente (`idempotency_key`) et reprenable.
- Provenance : toute affirmation sur une œuvre est un `Observation` ou une `Theory`
  (`primestone.provenance`) avec des `DocumentRef` exactes.

## Règles non négociables

- CANON / INTERPRETATION / THEORY / SPECULATION ne se mélangent jamais.
- Aucune analyse n'est COMPLETE s'il manque des pages (`missing_pages`).
- Aucune métrique privée de concurrent n'est inventée ; les données de marché portent une
  `DataClass`.
- Un script avec une erreur factuelle majeure n'est jamais validé, quel que soit son score.
- Les statuts NOT IMPLEMENTED / IMPLEMENTED / TESTED / VALIDATED / BLOCKED sont tenus à jour
  dans ROADMAP.md. « Le code existe » ≠ VALIDATED.

## Git

- Jamais de push direct sur `main`, jamais de force push, jamais de suppression de branche
  sans autorisation, jamais de fusion automatique.
- Branches : `feature/*`, `fix/*`, `release/*` (ou la branche imposée par la session).
- Une PR par fonctionnalité importante, en suivant `.github/pull_request_template.md`.
- Commits conventionnels : `feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`, `ci:`.

## Sécurité et coûts

- Aucun secret dans le dépôt ni dans les logs. Secrets → Secret Manager.
- Aucun PDF de comic, aucune donnée personnelle dans Git ou dans les fixtures.
- Mode zéro coût actif par défaut (`PRIMESTONE_ZERO_COST=true`) : ne jamais le désactiver
  sans demande explicite du propriétaire.
- Aucune ressource GCP créée, aucun déploiement, aucune migration en environnement partagé,
  aucun traitement massif ou appel payant sans approbation explicite de l'utilisateur.
- La CI n'appelle jamais de fournisseur payant : `FakeLLMProvider` et fixtures uniquement.
- Migrations : additives et réversibles. Toute migration destructive exige un ADR, une
  sauvegarde vérifiée et l'accord explicite de l'utilisateur.
- Ne pas installer d'outils ou de modèles arbitraires : justifier toute nouvelle dépendance.

## Méthode de livraison

1. Plan → 2. implémentation dans une branche → 3. tests (`make check` + intégration)
→ 4. mise à jour docs/ROADMAP/ADR → 5. PR complète → 6. attente d'approbation humaine.
