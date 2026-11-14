# PRIMESTONE EDITORIAL 2.0

Plateforme cloud d'intelligence éditoriale spécialisée dans les comics : analyse forensique
d'une bibliothèque de comics, mémoire de connaissances prouvées, compréhension des marchés
francophone et anglophone, scripts de très haute qualité en français et en anglais, et
apprentissage à partir des performances réelles des contenus Primestone.

> **Coût nul par défaut** : mode zéro coût actif, aucun fournisseur payant n'est appelé
> (transcription humaine ou modèle local gratuit). Voir [COSTS.md](COSTS.md).
>
> **Usage personnel, non commercial.** Les comics analysés restent privés (jamais versionnés,
> jamais redistribués). Voir [SECURITY.md](SECURITY.md).

## État actuel

| Élément | Statut |
|---|---|
| Phase 0 — Audit et architecture | VALIDATED ([rapport](docs/audit/phase-0.md)) |
| Phase 1 — Socle (monorepo, CI, file de tâches, passerelle IA simulée, API, web) | TESTED |
| Phase 2 — Comic Library (import par lots, validation, rendu, reprise) | TESTED |
| Phase 3 — Comic Vision (cases, ordre de lecture, texte et locuteurs via fournisseur IA) | TESTED — banc réel BLOCKED |
| Phase 4 — Forensic Intelligence (règles déterministes, transcription humaine, coût nul) | TESTED |
| Phase 5 — Knowledge Intelligence (graphe prouvé, corrections, recherche hybride gratuite) | TESTED |
| Phase 6 — Editorial Director (Chief Editor, agents, Fact Checker bloquant, validation humaine) | TESTED |
| Phase 7 — Research et Theory Laboratory (preuves vérifiées, contre-preuves, confiance expliquée) | TESTED |
| Phase 8 (+ 2b) — Market Intelligence (données publiques gratuites, écart EN→FR expliqué) | TESTED — collecte réelle BLOCKED (clé YouTube gratuite à créer) |
| Phases 9 à 13 | NOT IMPLEMENTED — voir [ROADMAP.md](ROADMAP.md) |
| Infrastructure GCP | Non provisionnée (en attente d'autorisation explicite) |

## Démarrage rapide

```bash
make install       # uv sync + pnpm install
make db            # PostgreSQL 16 + pgvector (Docker)
make migrate       # migrations Alembic
make check         # lint + types + tests (Python et web)

# Importer et traiter un dossier de comics (PDF/CBZ) localement
uv run primestone-library import ~/Comics --process
```

Détails : [DEVELOPMENT.md](DEVELOPMENT.md).

## Structure

```
apps/api/          API FastAPI versionnée (/api/v1)
apps/worker/       Worker des traitements asynchrones
apps/web/          Interface Next.js + Tailwind
packages/primestone/  Cœur métier : provenance, passerelle IA, file de tâches, modules
db/migrations/     Migrations Alembic versionnées
prompts/           Prompts versionnés
eval/              Corpus de référence et fixtures de test
docs/              ADR, architecture, modules, opérations
```

## Documentation

[ARCHITECTURE](ARCHITECTURE.md) · [ROADMAP](ROADMAP.md) · [DATA_MODEL](DATA_MODEL.md) ·
[API](API.md) · [SECURITY](SECURITY.md) · [COSTS](COSTS.md) · [DEVELOPMENT](DEVELOPMENT.md) ·
[TESTING](TESTING.md) · [CONTRIBUTING](CONTRIBUTING.md) · [CLAUDE](CLAUDE.md) ·
[ADR](docs/adr/) · [Opérations](docs/operations/)
