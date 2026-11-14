# ADR-0014 — Laboratoire des théories : preuves vérifiées, confiance calculée, jamais CANON

- Statut : Accepté
- Date : 2026-11-14

## Contexte

Le projet exige que CANON / INTERPRÉTATION / THÉORIE / SPÉCULATION ne se mélangent jamais, et
que toute théorie porte preuves, contre-preuves, alternatives et un niveau de confiance. Le
propriétaire veut un coût nul.

## Décision

1. **Modèle dédié** (migration 0007, additive et réversible) : `theory`, `theory_evidence`
   (rôle SUPPORTS/REFUTES, document, page, case, extrait, niveau, note, origine, retrait daté),
   `theory_alternative`, `theory_event` (journal append-only). Une contrainte en base interdit
   `level = 'CANON'` sur une théorie.
2. **Preuve vérifiée à l'entrée** : la page doit exister ; un extrait cité sur une page
   transcrite DOIT figurer dans la transcription servie (sinon refus) ; sur une page non
   transcrite il est accepté mais marqué non vérifié. Une preuve INTERPRETATION ou SPECULATION
   exige une note. À la lecture, chaque extrait est revérifié (`still_found`) : une
   transcription corrigée rend la preuve obsolète, signalée — jamais effacée.
3. **Calcul transparent** (`lab-confidence@1`, `primestone.lab.scoring`) : poids par preuve
   (CANON vérifiée 1.0, visuelle 0.8, non vérifiable 0.6, interprétation 0.4, spéculation 0.1) ;
   confiance = soutien / (soutien + contre + 1) ; plafonnée à 0.5 tant que la recherche de
   contre-preuves n'a pas été faite. Niveau THEORY seulement avec une preuve CANON solide ET
   une recherche de contre-preuves ; sinon SPECULATION. Statuts OPEN / SUPPORTED / CONTESTED /
   REFUTED. L'explication du calcul est renvoyée avec chaque théorie.
4. **Theory Researcher gratuit** : recherche hybride (ADR-0012) sur l'énoncé et les sujets,
   contradictions candidates et affirmations forensiques des sujets. Il **propose** ; seul un
   humain classe un passage pour ou contre. Sa recherche horodate `counter_search_at`.
5. **Missions du Chief Editor** : `THEORY_REVIEW` (revue avec recommandation : maintenir,
   rétrograder, contestée, réfutée, à corriger) et `RESEARCH_DOSSIER` (question → sources
   citées). Les deux livrables passent le Fact Checker bloquant (ADR-0013) ; l'énoncé de la
   théorie est présenté comme note, jamais comme fait.
6. **Rien n'est effacé** : retrait avec motif, journal de chaque action et du score résultant.

## Conséquences

- Une théorie ne monte jamais en CANON ; l'utilisateur voit pourquoi elle a son niveau.
- La confiance est une heuristique explicite, pas une probabilité : documentée comme telle.
- Les candidats du chercheur sont lexicaux/sémantiques : ils ne savent pas si un passage
  soutient ou contredit ; c'est assumé (pas de jugement automatique sans modèle).
- Limite : pas encore de citations « par œuvre » hors bibliothèque (phase 10).
