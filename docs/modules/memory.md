# Droits, mémoire éditoriale et coûts (phase 24)

ADR-0031 · paquet `primestone.memory` · migration 0019.

## Ce que fait le module

- Registre des droits et sources ; contrôle des citations de cases avant validation finale
  et diffusion.
- Leçons apprises uniquement depuis une preuve OBSERVED ou DEMONSTRATED ; journal unique.
- Tableau des coûts par mission et par émission (journaux réels).

## Utilisation

```bash
uv run primestone-memory rights-check SCRIPT_ID
uv run primestone-memory rights-add droit.json
uv run primestone-memory lesson "Les accroches-questions retiennent mieux" experiment EXPERIMENT_ID
uv run primestone-memory journal
uv run primestone-memory costs
```

`droit.json` : `{"kind": "PANEL_QUOTE", "subject": "Despair sourit", "source": "Sandman 1",
"basis": "QUOTATION", "proof": "citation illustrant l'analyse", "limits": "une case, durée
courte", "document_title": "Sandman 1", "page_number": 12, "panel_number": 3}`.

Web : `/memory`.

## Limites

- Le registre ne dit pas si une citation est licite : décision humaine.
- Les coûts ne couvrent que ce qui est journalisé (agents, vision).
