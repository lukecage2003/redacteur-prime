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
| `social` | 9 | déclinaisons par plateforme depuis les faits vérifiés ([fiche](social.md)) | TESTED (coût nul) |
| `storytelling` | 10 | scripts en 13 étapes, pré-notation, veto factuel ([fiche](storytelling.md)) | TESTED (coût nul) |
| `performance` | 11 | chaîne Primestone, import Studio, boucle d'apprentissage ([fiche](performance.md)) | TESTED (coût nul) |
| `voice` | 12 | STT/TTS locaux, 5 personnalités, réponses vérifiées ([fiche](voice.md)) | TESTED (banc réel BLOCKED) |
| `governance` | 20 | marque, piliers, politiques, décisions du fondateur ([fiche](governance.md)) | TESTED (coût nul) |
