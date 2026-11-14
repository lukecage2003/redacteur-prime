# ADR-0017 — Maximum Storytelling : scripts en 13 étapes, pré-notation explicable, veto factuel

- Statut : Accepté
- Date : 2026-11-14

## Décision

1. **Script = entité durable** (migration 0009, additive) :
   - `script` : langue fr/en, étape parmi 13, statut, `adapted_from` ;
   - `script_version` : en ajout seul, jamais modifiée ;
   - `script_score` : 8 critères, total, `factual_veto` ;
   - `script_event` : journal.
2. **13 étapes** : BRIEF → RESEARCH → ANGLE → HOOK → STRUCTURE → OUTLINE → DRAFT → FACT_CHECK →
   REWRITE → ORALITY → CRITIQUE → ADAPTATION → FINAL_VALIDATION. Retour possible à n'importe
   quelle étape, avec un motif. La validation finale exige que la dernière version ait été
   évaluée, **sans veto** et avec au moins 70/100, puis une décision humaine.
3. **Pré-notation `script-score@1`** (déterministe, gratuite) sur les 8 critères du projet
   (Hook 15, Architecture 15, Rétention 15, Écriture 15, Originalité 10, Oralité 10,
   Exactitude 15, Conclusion 5). Chaque critère est noté et expliqué. Elle est présentée comme
   une **heuristique**, à confirmer par une relecture humaine en aveugle (critère de la
   ROADMAP).
4. **Veto factuel absolu** : une erreur majeure du Fact Checker (citation absente, référence
   invalide, âge contredit) met l'exactitude à 0 et rend la validation impossible, quelle que
   soit la note, côté service comme côté approbation.
5. **Citations par œuvre** (« Titre (année) »), observation tirée des scripts fournis : elles
   sont classées *dans la bibliothèque* (à vérifier) ou *à sourcer* (savoir externe), jamais
   présentées comme vérifiées.
6. **Import PDF gratuit** (pypdfium2, déjà présent) : les lignes sont lues dans l'**ordre de
   lecture**, selon leur position sur la page. Sur un vrai script, l'ordre du flux PDF
   regroupait les titres à part.
7. **Adaptation FR/EN** : un script à part entière (ses propres angles), relié à l'original,
   qui suit tout le processus.
8. **Agents** Story Architect et Editorial Critic ; mission `SCRIPT_REVIEW`.

## Conséquences

- Aucune rédaction automatique : les versions sont écrites par l'humain. Un modèle local
  gratuit peut reformuler le livrable de critique (ADR-0013).
- Les heuristiques sont calibrées sur un seul vrai script (DESPAIR : 8 sections, 19,5 min
  estimées pour une cible de 18 à 22 min). À recalibrer avec les relectures humaines.
