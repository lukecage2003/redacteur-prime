# ADR-0012 — Graphe de connaissances dérivé des preuves, corrections journalisées, recherche gratuite

- Statut : Accepté
- Date : 2026-11-14

## Décision

1. **Entités et relations dérivées des observations forensiques**, sans modèle :
   - un personnage qui parle dans un comic ⇒ `APPEARS_IN` (CANON si l'attribution est humaine) ;
   - un nom écrit dans un comic ⇒ le comic `REFERENCES` le personnage (être cité ≠ apparaître) ;
   - « X se présente comme Y » ⇒ `REVEALS`, toujours INTERPRETATION ;
   - deux personnages qui parlent dans la même case ⇒ `RELATED_TO` (INTERPRETATION) ;
   - métadonnées d'import (série) ⇒ `RELATED_TO` INTERPRETATION, preuve « métadonnées d'import ».
   Chaque relation porte au moins une preuve (observation, document, page, case, extrait).
2. **Corrections humaines journalisées** (`correction`, motif obligatoire) : renommage, alias,
   fusion (l'entité absorbée pointe vers la conservée), retrait de relation (daté), relation
   manuelle (preuve obligatoire, THEORY refusée : phase 7). Rien n'est effacé ; une
   reconstruction respecte fusions et retraits.
3. **Graphe dans PostgreSQL** (ADR-0003) : voisinage et plus court chemin par CTE récursives,
   fusions résolues, relations retirées exclues.
4. **Recherche hybride gratuite** : plein texte PostgreSQL (`simple`, texte normalisé sans
   accents) + pgvector, fusion RRF. Plongements par défaut : n-grammes hachés (local, sans
   modèle ; tolère fautes et accents, **non sémantique**) ; option sémantique gratuite : modèle
   local via Ollama (`nomic-embed-text`). Seules les transcriptions servies sont trouvables.

## Conséquences

Coût nul. Le graphe vaut ce que valent les transcriptions et les corrections humaines ; il ne
« devine » rien. Pas d'index vectoriel (échelle personnelle : balayage exact) ; à ajouter avec
une dimension fixe si le volume l'exige.
