# ADR-0008 — Développement trunk-based

- Statut : Accepté
- Date : 2026-11-14

## Décision

`main` est la seule branche longue, protégée. Travail dans `feature/*`, `fix/*`, `release/*`,
fusion par PR (squash) après CI verte et approbation humaine. Pas de branche `develop` :
un seul contributeur, staging déployé depuis `main` ; une branche d'intégration n'apporterait
que des fusions supplémentaires.

## Conséquences

Historique linéaire. Une branche `develop` pourra être introduite par un nouvel ADR si plusieurs
contributeurs travaillent en parallèle sur des versions distinctes.
