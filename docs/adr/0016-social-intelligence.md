# ADR-0016 — Social Intelligence : déclinaisons depuis les faits vérifiés d'un livrable approuvé

- Statut : Accepté
- Date : 2026-11-14

## Décision

1. **Source** : seul un livrable **approuvé** et déclinable (dossier de personnage, audit de
   continuité, revue de théorie, dossier de recherche) peut être décliné (mission
   `SOCIAL_PACKAGE`).
2. **Faits repris mot pour mot** : seules les phrases VERIFIED par le Fact Checker sont reprises,
   avec leur référence. Les phrases non vérifiées sont écartées et comptées. Le paquet repasse
   le Fact Checker, puis l'approbation humaine.
3. **Pas de découpage mécanique** (`social-package@1`) :
   - chaque fait reçoit un rôle (TENSION, CLAIM, FACT) et sa section d'origine ;
   - YouTube long : un chapitre par section ;
   - TikTok : accroche par la tension, puis faits d'autres sections, puis question ;
   - Reels : sélection différente de TikTok (autre angle) ;
   - carrousel : 1 fait par carte, 20 cartes au plus.
4. **Formats datés** : limites des plateformes (date de vérification, source nommée,
   « à revérifier ») distinctes des durées cibles, qui sont des choix éditoriaux.
5. **Angle marché** facultatif : un sujet chiffré de Market Intelligence présent dans le
   livrable est indiqué (ESTIMATE).

## Conséquences

- Aucun texte inventé : les déclinaisons sont des trames sourcées, pas des scripts rédigés. La
  rédaction (hooks, voix) relève de la phase 10 ; un modèle local gratuit peut reformuler, mais
  son texte n'est retenu que s'il passe le Fact Checker (ADR-0013).
- Les formats doivent être revérifiés avant publication : ce conteneur n'a pas d'accès réseau
  aux aides des plateformes.
