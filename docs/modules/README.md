# Modules d'intelligence

Chaque module vit dans `packages/primestone/src/primestone/<module>/` et expose une interface
publique dans son `__init__.py`. Une fiche détaillée (entrées, sorties, limites, tests) est
ajoutée ici au démarrage de la phase correspondante.

| Module | Phase | Responsabilité | Statut |
|---|---|---|---|
| `provenance` (transverse) | 1 | niveaux d'évidence, références, complétude, classes de données | TESTED |
| `ai_gateway` (transverse) | 1 | fournisseurs interchangeables, budget, traçabilité | TESTED |
| `jobs` (transverse) | 1 | file durable, reprise après panne | TESTED |
| `comic` | 2 | bibliothèque, import, rendu ([fiche](comic-library.md)) | TESTED |
| `vision` | 3 | cases, ordre de lecture, texte, locuteurs ([fiche](comic-vision.md)) | TESTED (banc réel BLOCKED) |
| `forensic` | 4 | observations prouvées, contradictions, affirmations ([fiche](forensic.md)) | TESTED (coût nul) |
| `knowledge` | 5 | entités, relations prouvées, corrections, graphe, recherche ([fiche](knowledge.md)) | TESTED (coût nul) |
| `editorial` | 6 | Chief Editor, agents, Fact Checker, approbations ([fiche](editorial.md)) | TESTED (coût nul) |
| `lab` | 7 | théories, preuves et contre-preuves, confiance calculée ([fiche](lab.md)) | TESTED (coût nul) |
| `market` | 2b, 8 | sources avec fiche, collecte publique gratuite, écart EN→FR ([fiche](market.md)) | TESTED (collecte réelle BLOCKED) |
| `social` | 9 | stratégies et déclinaisons par plateforme | NOT IMPLEMENTED |
| `storytelling` | 10 | scripts en 13 étapes, notation, veto factuel | NOT IMPLEMENTED |
| `performance` | 11 | métriques autorisées, boucle d'apprentissage | NOT IMPLEMENTED |
| `voice` | 12 | streaming STT/TTS, personnalités | NOT IMPLEMENTED |
