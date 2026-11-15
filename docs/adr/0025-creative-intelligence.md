# ADR-0025 — Creative Intelligence : packaging honnête, charte versionnée, séries

- Statut : Accepté
- Date : 2026-11-15

## Décision

1. **Packaging (`packaging@1`)**, à partir des faits **vérifiés** d'un script évalué :
   - 10 titres, 5 concepts de miniature (décrits, pas générés), 3 promesses, 3 accroches ;
   - contrôle d'**honnêteté** : chaque nom propre du titre figure dans le script, aucun terme
     banni par la charte, une théorie n'est jamais annoncée sans être traitée ;
   - lisibilité (longueur, majuscules) et adéquation au niveau (pas de jargon en
     DISCOVERY) ;
   - **aucune prédiction de CTR ni de vues** : les meilleures candidates deviennent des
     propositions d'expériences (phase 14).

   Un modèle local facultatif (Ollama) peut proposer d'autres titres, soumis aux mêmes
   contrôles.
2. **Charte de marque versionnée** : couleurs, typographies, ton (à faire et à éviter),
   règles de miniatures, packaging, son, habillage.
   - Chaque version est conservée, ce qui permet de faire évoluer la charte sans perdre
     l'historique.
   - Par défaut, une charte de départ marquée « à personnaliser ».
   - Les miniatures sont contrôlées : nombre de mots, palette, termes bannis.
3. **Séries et franchises** :
   - promesse, identité, segment visé, ton, structure récurrente, durée cible, direction
     artistique, distribution, logique d'évolution ;
   - épisodes = scripts ;
   - cohérence mesurée : durée réelle face à la cible, structure retrouvée dans le script,
     note moyenne.
4. **Agent Brand & Packaging Editor**, mission `PACKAGING_REVIEW` (Fact Checker sur le
   livrable).

## Conséquences

- Les titres « accrocheurs » mais non soutenus par le script sont refusés, visiblement, avec
  leur motif.
- L'identité Primestone devient mesurable : la charte et les séries servent de référence
  aux autres modules.
