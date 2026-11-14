# Maximum Storytelling (phase 10)

Code : `packages/primestone/src/primestone/storytelling/` · ADR-0017 · coût : **nul**.

## Utilisation

```bash
uv run primestone-script create --title "Despair" --language fr script.pdf --documents ID…
uv run primestone-script evaluate SCRIPT_ID          # Fact Checker + note sur 100 + veto
uv run primestone-script step SCRIPT_ID REWRITE --reason "accroche trop longue"
uv run primestone-script version SCRIPT_ID v2.md
uv run primestone-script review SCRIPT_ID --process  # mission du Chief Editor
uv run primestone-script validate SCRIPT_ID          # validation finale humaine
uv run primestone-script adapt SCRIPT_ID script_en.md
```

Interface web : `/scripts`. API : `/api/v1/scripts` (création, versions, étapes, évaluations,
validations, adaptations).

## Format reconnu

- Sections horodatées : `00:00 - Titre`, `[1:02:03] Titre`, ou plage `1:35 - 4:00 | TITRE`.
  À défaut, titres `## …`. Ce qui précède le premier horodatage est le brief, pas du texte
  dit.
- Citations de page : `« … » [Titre, p. 12, case 3]`, vérifiées sur les transcriptions.
- Références d'œuvres : `Titre (année)`, classées *dans la bibliothèque* ou *à sourcer*.
- Fichiers `.md`, `.txt`, `.pdf` (texte extrait localement, dans l'ordre de lecture).

## Règles

- Les versions ne sont jamais effacées ; toute action est journalisée.
- **Veto factuel** : une erreur majeure rend la validation impossible, quel que soit le score.
- Validation finale : dernière version évaluée, sans veto, au moins 70/100, décision humaine.

## Essai réel (scripts fournis le 2026-11-14, non versionnés)

- **DESPAIR** :
  - 8 sections horodatées dans l'ordre, 2 930 mots, 19,5 min estimées pour une cible annoncée
    de 18 à 22 min ;
  - 3 références d'œuvres, à sourcer car absentes de la bibliothèque ;
  - pré-note 64/100 : exactitude 0 tant que les sources ne sont pas dans la bibliothèque ;
    architecture 15/15.
- **MARVEL_MAP_1** : guide sans horodatage, lu comme une seule section.
- Défaut corrigé grâce à cet essai : l'ordre du flux PDF regroupait les titres à part.

## Limites

- Pré-notation heuristique : à recalibrer sur les relectures humaines en aveugle.
- Pas de rédaction automatique des versions.

## Tests

- `packages/primestone/tests/test_storytelling_analysis.py`
- `apps/worker/tests/test_storytelling_pipeline.py`
- `apps/web/lib/scripts.test.ts`
