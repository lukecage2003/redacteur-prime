# DATA_MODEL

PostgreSQL 16 + pgvector. Migrations Alembic dans `db/migrations/versions/`. Schéma déclaré
dans `packages/primestone/src/primestone/db/schema.py` ; la CI vérifie (`alembic check`) que
les deux correspondent.

Légende : ✅ implémenté (migration 0001) · 🔜 prévu (phase indiquée).

## Invariants

1. Toute `observation`, `relation` et `theory` a au moins une preuve (`evidence_ref`).
2. `level` ∈ {CANON, INTERPRETATION, THEORY, SPECULATION} ; jamais de mélange dans un même enregistrement.
3. Une analyse de document n'est `COMPLETE` que si toutes ses pages sont traitées.
4. Les corrections sont en ajout seul : on remplace (`superseded_by`), on n'écrase pas.
5. Les données de marché/performance portent une `data_class` ∈ {PUBLIC, PRIVATE_AUTHORIZED, ESTIMATE, HYPOTHESIS}.
6. Tout résultat d'IA référence `prompt_id`, `prompt_version`, fournisseur, modèle et coût.

## Exécution ✅

| Table | Rôle | Colonnes clés |
|---|---|---|
| `pipeline_run` ✅ | Un lot / une mission de traitement | `kind`, `status` (PENDING/RUNNING/SUCCEEDED/FAILED/CANCELLED), `params` |
| `pipeline_step` ✅ | Étape idempotente et reprenable | `idempotency_key` (unique), `status` (PENDING/RUNNING/SUCCEEDED/FAILED/DEAD), `attempts`, `max_attempts`, `available_at`, `locked_at`, `locked_by`, `payload`, `result`, `error` |

## Bibliothèque ✅ (phase 2, migration 0002)

| Table | Colonnes clés |
|---|---|
| `comic` ✅ | `title`, `series_title`, `issue_number`, `language`, `expected_page_count` (> 0) |
| `document` ✅ | `comic_id`, `sha256` (unique, 64 car.), `format` (PDF/CBZ), `byte_size`, `storage_key`, `original_filename`, `page_count`, `status` (UPLOADED → VALIDATED → COMPLETE, ou INCOMPLETE / REJECTED / FAILED), `error` |
| `page` ✅ | `document_id`, `number` (unique par document), `status` (PENDING/RENDERED/FAILED), `render_key`, `render_profile`, `render_sha256`, `width`, `height`, `byte_size`, `error` |
| `import_item` ✅ | `run_id` (→ `pipeline_run`), `document_id`, `original_filename`, `outcome` (NEW/DUPLICATE/REJECTED), `error` |

Règle de complétude : un document n'est `COMPLETE` que si toutes ses pages 1..N sont `RENDERED`
et que N correspond à `expected_page_count` lorsqu'il est connu (sinon `INCOMPLETE`). Une page
illisible rend le document `FAILED`. La série est un simple texte pour l'instant ; elle deviendra
une entité `SERIES` du graphe en phase 5.

## Vision 🔜 (phase 3)

| Table | Colonnes clés |
|---|---|
| `panel` | page, `index`, `bbox` (normalisée), ordre de lecture |
| `text_region` | page, panel, `kind` (dialogue/narration/onomatopée/légende), texte, langue, locuteur, `bbox`, confiance OCR |

## Analyse 🔜 (phase 4)

| Table | Colonnes clés |
|---|---|
| `observation` | `statement`, `kind` (personnage, objet, symbole, événement…), `level`, `confidence`, `agent_run_id` |
| `evidence_ref` | cible polymorphe (observation/relation/theory), `document_id`, `page`, `panel`, `bbox`, `excerpt`, `role` (SUPPORTS/REFUTES) |

## Connaissance 🔜 (phase 5)

| Table | Colonnes clés |
|---|---|
| `entity` | `type` (CHARACTER, EVENT, LOCATION, OBJECT, CONCEPT, SERIES, CONTINUITY, COMIC), nom canonique |
| `entity_alias` | entité, alias, langue |
| `relation` | source, cible, `type` (APPEARS_IN, REFERENCES, CONTRADICTS, PRECEDES, REVEALS, FORESHADOWS, RELATED_TO, OPPOSES), `level`, confiance |
| `correction` | cible, ancienne valeur, nouvelle valeur, auteur, motif, `superseded_by` |
| `embedding` | cible, `model`, `dimension`, `vector` (pgvector, index HNSW) |
| recherche plein texte | colonnes `tsvector` FR et EN générées, index GIN |

Le graphe est stocké en PostgreSQL (`entity` + `relation`, requêtes récursives) — ADR-0003.

## Théories 🔜 (phase 7)

`theory` (titre, thèse, `level` THEORY/SPECULATION, confiance, `counter_evidence_searched`),
`theory_alternative`, preuves et contre-preuves via `evidence_ref`.

## Éditorial et agents 🔜 (phases 6, 10)

`mission`, `mission_task`, `agent_run` (agent, entrées/sorties JSON validées, `prompt_id`,
`prompt_version`, fournisseur, modèle, jetons, coût, latence, erreur), `approval_request`,
`research_dossier`, `script`, `script_version` (langue, contenu, étape), `script_score`
(8 critères + `factual_veto`).

## Marché et performance 🔜 (phases 2b, 8, 11)

`market_source` (fiche : accès, quotas, conditions, date de vérification), `market_signal`
(source, sujet, langue, valeur, unité, `data_class`, `observed_at`), `content_item`,
`performance_metric` (série temporelle, comptes autorisés uniquement).

## Voix 🔜 (phase 12)

`voice_session`, `voice_turn` (transcription, réponse, latences), `pronunciation_lexicon`.
