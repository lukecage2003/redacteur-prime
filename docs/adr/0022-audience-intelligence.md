# ADR-0022 — Audience Intelligence : segments prouvés, graphe d'audience distinct, communauté anonyme

- Statut : Accepté
- Date : 2026-11-15

## Décision

1. **Segment = motivations + niveau de connaissance** (NOVICE, INTERMEDIATE, EXPERT). L'âge
   n'est pas un champ, et un nom ou une motivation fondés sur l'âge sont refusés.
2. **Statut calculé, jamais déclaré** :
   - CONFIRMED seulement avec des preuves **observées** actives d'au moins **deux natures**
     différentes (METRIC, COMMENT_CLUSTER, MARKET) ;
   - une déclaration (DECLARED) reste une HYPOTHESIS ;
   - le retrait d'une preuve recalcule le statut.
3. **Graphe d'audience** (`audience_link`) : arêtes segment → entité du graphe de
   connaissances, sujet de marché, format ou plateforme. Chaque arête porte une preuve du
   **même** segment. Elle est stockée **à part** du graphe de l'œuvre : les preuves d'audience
   (statistiques, commentaires) ne se mélangent jamais aux preuves canoniques (pages).
4. **Communauté** (`community@1`) :
   - commentaires publics des vidéos **de la chaîne**, via YouTube Data API (clé gratuite) ou
     import ;
   - **aucune identité d'auteur conservée** (nom, chaîne, photo ignorés), conformément au
     principe de minimisation et à la présence possible de mineurs ;
   - classement QUESTION, THEORY, REQUEST, CONTROVERSY, PRAISE ou OTHER ;
   - récurrence à partir de 3 commentaires ;
   - **propositions uniquement**, jamais de publication ni de réponse automatique.
5. **Agent Audience Analyst**, mission `AUDIENCE_BRIEF` : NE PAS VALIDER sans segment
   confirmé.

## Conséquences

- Les segments démarrent en hypothèses. Ils se confirment avec les statistiques autorisées
  (phase 14) et les commentaires.
- Reddit et les forums restent hors périmètre tant qu'aucun accès officiel n'est approuvé.
