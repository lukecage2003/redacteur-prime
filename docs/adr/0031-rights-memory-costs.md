# ADR-0031 — Droits et sources, mémoire éditoriale prouvée, coûts

- Statut : Accepté
- Date : 2026-11-15
- Contexte : [audit « média autonome »](../audit/autonomous-media-brand.md), phase 24.

## Décision

1. **Registre des droits** (`rights_record`) : nature (case citée, image, musique, voix,
   vidéo, texte), sujet, source, base invoquée (citation, licence, permission, œuvre propre,
   domaine public), licence nommée si base LICENSE, preuve, limites, échéance, statut
   (ACTIVE/WITHDRAWN). Le registre **trace** ; il ne juge pas la légalité.
2. **Citations de cases** : une citation « [Titre, p. N, case M] » désigne une image montrée.
   La validation finale d'un épisode (`SCRIPT_FINAL_VALIDATION`) et l'approbation d'une
   diffusion (`DISTRIBUTION_PLAN`) sont refusées tant qu'une case citée n'a pas de droit actif
   et non échu (même document, page et case ; ou droit rattaché au script). Les citations de
   page seules restent des sources.
3. **Mémoire éditoriale** (`editorial_lesson`) : une leçon n'est enregistrée que depuis une
   preuve OBSERVED (statistiques autorisées en base pour le contenu) ou DEMONSTRATED
   (expérience CONCLUDED avec gagnant) ; la preuve est copiée dans la leçon. Contrainte en
   base sur le niveau de preuve. Une leçon se retire (motif), jamais ne s'efface.
4. **Journal unique** : décisions de gouvernance et leçons, ordonnées dans le temps.
5. **Coûts** : lus dans les journaux existants (`agent_run`, `page_analysis`), par mission et
   par émission ; mode zéro coût affiché. Aucune nouvelle table, aucune estimation inventée.

## Conséquences

- La règle de reconnaissance des citations est partagée avec le Fact Checker (même forme),
  recopiée dans `memory.rights` pour éviter un cycle d'import.
