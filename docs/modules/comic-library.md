# Module Comic Library (phase 2)

Code : `packages/primestone/src/primestone/comic/` · Étapes worker : `apps/worker/src/primestone_worker/library.py`
· API : `apps/api/src/primestone_api/routes/library.py` · CLI : `primestone-library`.

## Rôle

Constituer une bibliothèque fiable de comics (PDF, CBZ) : import par lots de 50 fichiers ou plus,
validation, déduplication, rendu de chaque page en image, et état exact de chaque document.
C'est la source de toutes les références documentaires des phases suivantes
(`DocumentRef(document_id, page, …)`).

## Pipeline

```
import (synchrone)            empreinte SHA-256 → stockage originals/… → document (ou doublon)
  └─ library.validate         signature, PDFium / zip sûr, nombre de pages, pages attendues
       └─ library.render_page ×N   WebP (profil versionné) → page RENDERED
                                   → document COMPLETE quand AUCUNE page ne manque
```

## Entrées / sorties

| Entrée | Sortie |
|---|---|
| Fichiers locaux (CLI) ou téléversés (API), métadonnées facultatives (titre, série, numéro, langue, pages attendues) | `pipeline_run` (lot), `import_item` par fichier, `comic`, `document`, `page`, rendus WebP, rapport de lot |

## Statuts d'un document

| Statut | Signification |
|---|---|
| UPLOADED | stocké, en attente de validation |
| VALIDATED | valide, rendu en cours |
| COMPLETE | toutes les pages rendues, nombre de pages conforme |
| INCOMPLETE | moins (ou plus) de pages que le nombre attendu : jamais COMPLETE |
| REJECTED | fichier invalide (corrompu, chiffré, vide, trop gros, sans page…) |
| FAILED | au moins une page illisible |

## Limites et garde-fous

Taille par fichier (1 Gio), pages par document (2 000), pixels par image (150 M), entrée d'archive
(200 Mio), taux de compression (200:1), 200 fichiers par requête API. Voir SECURITY.md.

## Métadonnées ComicInfo.xml

Pour un CBZ, `ComicInfo.xml` (≤ 1 Mo) complète ce que l'utilisateur n'a pas précisé : titre
(« Série #Numéro »), série, numéro, langue et **nombre de pages attendu** (un document plus
court ne sera jamais COMPLETE). Un fichier absent, mal formé ou porteur d'un DOCTYPE/ENTITY est
ignoré, jamais bloquant.

## Hors périmètre

URL signées Cloud Storage (lecture via l'API) ; édition des métadonnées depuis le web.
