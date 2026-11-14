# Module Knowledge Intelligence (phase 5) — coût nul

Code : `packages/primestone/src/primestone/knowledge/` · CLI : `primestone-knowledge`
· API : `/api/v1/knowledge/*`, `/api/v1/search` · Web : `/knowledge`, `/knowledge/{id}`.

## Chaîne

```
transcriptions (humaines / modèle local) → forensique (règles) → entités + relations prouvées
                                                               → index de recherche hybride
corrections humaines (journalisées) ─────────────────────────────┘ (respectées à chaque reconstruction)
```

## Utilisation

```bash
uv run primestone-forensic analyze --documents <T1> <T2>
uv run primestone-knowledge build --documents <T1> <T2>
uv run primestone-knowledge entities --type CHARACTER
uv run primestone-knowledge search "Catwomen"              # tolère les fautes
uv run primestone-knowledge path <ID_A> <ID_B>
uv run primestone-knowledge merge <GARDER> <ABSORBER> --reason "même personnage"
uv run primestone-knowledge retract <RELATION> --reason "ironie, pas un aveu"
```

Web : `/knowledge` → « Construire depuis la bibliothèque », recherche, fiches d'entité avec
relations, preuves (liens vers les pages), alias, renommage, fusion, retrait, historique.

## Relations produites

| Type | Origine | Niveau |
|---|---|---|
| APPEARS_IN | le personnage parle dans le comic | CANON si attribution humaine, sinon INTERPRETATION |
| REFERENCES | le nom est écrit dans le comic | niveau de la transcription |
| REVEALS (« se présente comme ») | affirmation d'identité | toujours INTERPRETATION |
| RELATED_TO (« parlent dans la même case ») | co-présence de répliques | INTERPRETATION |
| RELATED_TO (« fait partie de la série ») | métadonnées d'import | INTERPRETATION |
| tout type, saisi à la main | humain, avec preuve | CANON / INTERPRETATION / SPECULATION |

## Recherche

Plein texte + similarité vectorielle fusionnés (RRF). Plongement par défaut gratuit et local
(n-grammes hachés, `hashing-ngram-256@2`), mesuré : faute de frappe ≈ 0,56–0,67 de similarité,
texte sans rapport ≤ 0,12. Pour une recherche sémantique (synonymes, paraphrases) :
`PRIMESTONE_EMBEDDER=ollama` + `ollama pull nomic-embed-text` (gratuit, local).

## Limites

Pas encore de lieux, objets, événements (nécessitent une analyse visuelle ou des
transcriptions plus riches) ; pas d'ordre de publication automatique (`PRECEDES` à saisir
à la main avec preuve).
