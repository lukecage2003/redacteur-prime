# ADR-0001 — Monolithe modulaire en monorepo

- Statut : Accepté
- Date : 2026-11-14

## Contexte

Neuf intelligences (comic, forensic, knowledge, editorial, market, social, storytelling,
performance, voix) coordonnées par un Chief Editor. Un seul développeur, usage personnel,
budget contraint. Les modules partagent fortement le modèle de provenance et la base.

## Décision

Un monorepo ; un paquet Python `primestone` contenant un sous-paquet par intelligence ;
trois points d'entrée déployables : `apps/api`, `apps/worker`, `apps/web`. Workspace `uv` pour
Python, `pnpm` pour le web.

## Alternatives considérées

- **Microservices dès le départ** : coût d'exploitation, latence réseau, transactions
  distribuées, versionnement des contrats — sans bénéfice à cette échelle.
- **Dépôts séparés par module** : duplication du modèle de provenance, synchronisation pénible.

## Conséquences

- Refactorisation transverse simple, une seule CI.
- Discipline de dépendances nécessaire (règles dans ARCHITECTURE.md).
- Extraction d'un service (ex. voix temps réel) possible plus tard si la charge ou l'isolation
  l'exige — sur la base de mesures, avec un nouvel ADR.
