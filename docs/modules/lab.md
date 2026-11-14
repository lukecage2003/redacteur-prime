# Research et Theory Laboratory (phase 7)

Code : `packages/primestone/src/primestone/lab/` · ADR-0014 · coût : **nul**.

## Rôle

Éprouver une hypothèse sur une œuvre sans jamais la confondre avec le canon : preuves pour,
contre-preuves, explications alternatives, confiance calculée et expliquée, historique complet.

## Entrées / sorties

| Action | Service (`TheoryLab`) | API | CLI (`primestone-lab`) |
|---|---|---|---|
| Créer | `create(title, claim, document_ids, subjects, author)` | `POST /lab/theories` | `create` |
| Lister | `theories(status, level)` | `GET /lab/theories?status=&level=` | `list` |
| Détail | `theory(id)` (preuves, `still_found`, alternatives, journal, calcul) | `GET /lab/theories/{id}` | `show` |
| Preuve | `add_evidence(...)` | `POST /lab/evidence` | `evidence` |
| Retrait | `retract_evidence(id, reason)` | `POST /lab/evidence/retractions` | `retract` |
| Alternative | `add_alternative(id, text)` | `POST /lab/alternatives` | `alternative` |
| Contre-preuves | `research(id)` (Theory Researcher) | `POST /lab/research` | `research` |
| Revue | mission `THEORY_REVIEW` | `POST /editorial/missions` | `review [--process]` |
| Question | mission `RESEARCH_DOSSIER` | `POST /editorial/missions` | `ask --question` |

Interface web : `/lab` (liste, création) et `/lab/{id}` (preuves, retrait motivé,
alternatives, recherche de contre-preuves, revue par le Chief Editor, historique).

## Règles

- Niveau **THEORY** seulement avec ≥ 1 preuve CANON solide (extrait vérifié, ou preuve visuelle
  attestée) **et** une recherche de contre-preuves faite ; sinon **SPECULATION**. Jamais CANON
  (contrainte en base).
- Extrait absent d'une page transcrite ⇒ preuve refusée. Page non transcrite ⇒ acceptée, non
  vérifiée, poids réduit.
- Confiance `lab-confidence@1` = soutien / (soutien + contre + 1), plafonnée à 0.5 sans
  recherche de contre-preuves. Ce n'est pas une probabilité.
- Le Theory Researcher propose des passages et des contradictions candidates ; il ne classe
  jamais. La revue du Chief Editor recommande, l'humain décide (approbation).

## Limites

- Candidats trouvés par recherche lexicale/sémantique locale : pertinence, pas jugement.
- Sources hors bibliothèque (savoir externe, citations par œuvre) : non gérées (phase 10).
- Validation sur la bibliothèque réelle : à faire (NOT VALIDATED).

## Tests

`packages/primestone/tests/test_lab_scoring.py` (calcul), `apps/worker/tests/test_lab_pipeline.py`
(cycle complet, obsolescence après correction, contrainte CANON, missions de revue et de
recherche), `apps/api/tests/test_lab_api.py`, `apps/web/lib/lab.test.ts`.
