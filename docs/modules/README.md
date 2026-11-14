# Modules d'intelligence

Chaque module vit dans `packages/primestone/src/primestone/<module>/` et expose une interface
publique dans son `__init__.py`. Une fiche détaillée (entrées, sorties, limites, tests) est
ajoutée ici au démarrage de la phase correspondante.

| Module | Phase | Responsabilité | Statut |
|---|---|---|---|
| `provenance` (transverse) | 1 | niveaux d'évidence, références, complétude, classes de données | TESTED |
| `ai_gateway` (transverse) | 1 | fournisseurs interchangeables, budget, traçabilité | TESTED |
| `jobs` (transverse) | 1 | file durable, reprise après panne | TESTED |
| `comic` | 2–3 | bibliothèque, import, rendu, OCR, cases | NOT IMPLEMENTED |
| `forensic` | 4 | observations prouvées par page et par case | NOT IMPLEMENTED |
| `knowledge` | 5 | entités, relations, corrections, recherche hybride | NOT IMPLEMENTED |
| `editorial` | 6–7 | Chief Editor, agents, théories, approbations | NOT IMPLEMENTED |
| `market` | 2b, 8 | sources, signaux, écart EN→FR | NOT IMPLEMENTED |
| `social` | 9 | stratégies et déclinaisons par plateforme | NOT IMPLEMENTED |
| `storytelling` | 10 | scripts en 13 étapes, notation, veto factuel | NOT IMPLEMENTED |
| `performance` | 11 | métriques autorisées, boucle d'apprentissage | NOT IMPLEMENTED |
| `voice` | 12 | streaming STT/TTS, personnalités | NOT IMPLEMENTED |
