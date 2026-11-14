# Module Comic Vision (phase 3)

Code : `packages/primestone/src/primestone/vision/` · Étape worker : `vision.analyze_page`
· API : `/api/v1/vision/*`, `/api/v1/library/documents/{id}/pages/{n}/analysis`
· CLI : `primestone-vision` · Web : `/library/{id}/pages/{n}`.

## Pipeline par page

```
rendu WebP ─► détection des cases (local, xycut-2, redressement) ─► ordre de lecture
          └─► fournisseur vision (texte, type, langue, locuteur) ─► rattachement aux cases
          ─► page_analysis + panel + text_region (ajout seul, coût et versions tracés)
```

## Utilisation

```bash
uv run primestone-vision estimate --documents <ID> --provider claude          # coût estimé, rien n'est lancé
uv run primestone-vision analyze  --documents <ID> --provider claude --budget 2 --process
uv run primestone-vision show <ID> 1                                          # cases + textes de la page 1
uv run primestone-vision benchmark-panels --pages 200 [--gutter-crossing]     # banc d'essai du détecteur
```

Le fournisseur `claude` nécessite une clé d'API Anthropic (variable `ANTHROPIC_API_KEY` ou profil
`ant auth login`) et n'est **jamais** appelé par la CI.

## Garanties

| Règle | Mise en œuvre |
|---|---|
| Pas de dépense non autorisée | estimation préalable, refus au-delà du budget, budget revérifié avant chaque appel |
| Jamais payé deux fois | `analysis_key` unique (rendu, détecteur, fournisseur, modèle, prompt, sens de lecture) |
| Traçabilité | fournisseur, modèle réellement servi, version de prompt, jetons, coût, latence par analyse |
| Pas d'invention | prompt : transcription exacte, pas de locuteur deviné hors page ; boîtes hors page écartées |
| Incertitude visible | confiance par texte et par locuteur ; l'interface signale les transcriptions < 0,8 |
| Échecs | refus / sortie tronquée : analyse FAILED enregistrée, pas de nouvel essai payant ; erreurs réseau : nouvelles tentatives |

## Mesures du détecteur de cases (2026-11-14, 200 planches synthétiques)

| Cas | Précision | Rappel | F1 | Ordre |
|---|---|---|---|---|
| Pages droites (LTR + RTL, fonds clairs et sombres, cases bordées et en aplat) | 1,000 | 1,000 | 1,000 | 100 % |
| Bruit gaussien σ = 8, JPEG q70, inclinaison ≤ 1,5° | — | — | 1,000 | — |
| Bulle à cheval sur une gouttière | 0,826 | 0,492 | 0,617 | 99,9 % |

≈ 30 ms par page sur 1 vCPU. Limites : bulles qui chevauchent les gouttières, cases qui se
chevauchent, gouttières non rectilignes → renvoyées comme une case englobante.

## Essai sur de vrais comics (2026-11-14, fichiers privés, non versionnés)

3 numéros réels fournis par le propriétaire (79 pages) : import, validation et rendu sans erreur
en 7,8 s (≈ 0,33 Mo par page rendue) ; détection des cases sur les 79 pages en 6,1 s.
Vérification visuelle de 5 pages : cases et ordre de lecture corrects sur les planches
classiques (5, 6, 6 cases) et sur une grille irrégulière de 15 cases (4×4 avec une case
double) ; couvertures et pleines pages = 1 case. Un faux positif relevé : le bloc de mentions
légales de la page de crédits est pris pour une case (amélioration possible : écarter les
bandes de texte très plates en marge). Le lettrage est en capitales (« I AM T'CHALLA, THE
BLACK PANTHER ») : la règle d'identité de la phase 4 (nom connu exigé en capitales) est
pertinente.

## Reste à faire pour VALIDATED

Banc d'essai sur un corpus réel annoté (cases, textes, locuteurs) : F1 des cases, CER de la
transcription, exactitude des types et des locuteurs, coût réel par page — fonctions prêtes dans
`primestone.vision.evaluation`. Nécessite : quelques pages annotées et un budget d'appels.
