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

## Vision ✅ (phase 3, migration 0003)

| Table | Colonnes clés |
|---|---|
| `page_analysis` ✅ | `page_id`, `run_id`, `render_sha256` (l'analyse vaut pour tout rendu identique), `analysis_key` (unique : rendu + détecteur + fournisseur + modèle + prompt + sens), `status` (SUCCEEDED/FAILED), `detector`, `provider`, `model`, `prompt_version`, `reading_direction`, `cost_usd`, `input_tokens`, `output_tokens`, `latency_ms`, `error` |
| `panel` ✅ | `analysis_id`, `index` (ordre de lecture), `x`, `y`, `width`, `height` (normalisés) |
| `text_region` ✅ | `analysis_id`, `order`, `panel_index` (NULL : hors case), `kind` (DIALOGUE, THOUGHT, NARRATION, SFX, CAPTION, OTHER), `text`, `language`, `confidence`, `speaker`, `speaker_confidence`, boîte normalisée |

Ajout seul : une nouvelle version de détecteur, de modèle ou de prompt crée une nouvelle analyse ;
la plus récente réussie est servie. Référence documentaire d'un texte :
`DocumentRef(document_id, page, panel=panel_index, bbox)`.

## Analyse ✅ (phase 4, migration 0004)

| Table | Colonnes clés |
|---|---|
| `observation` ✅ | `observation_key` (unique, stable), `extractor` (version), `kind` (LETTERING, SPEECH, MENTION, CLAIM, FIRST_APPEARANCE, ALIAS_CANDIDATE, CONTRADICTION_CANDIDATE), `level` (CANON/INTERPRETATION/THEORY/SPECULATION), `subject`, `predicate`, `value`, `statement`, `confidence`, `run_id` |
| `evidence_ref` ✅ | `observation_id`, `document_id`, `page_number`, `panel_index`, `analysis_id`, `text_region_id`, boîte, `excerpt`, `role` (SUPPORTS/REFUTES) |

Une observation est « courante » si toutes ses preuves proviennent des analyses servies
aujourd'hui ; une correction humaine rend les anciennes caduques sans les effacer. Les
transcriptions humaines sont des `page_analysis` de fournisseur `human` (coût nul).

## Connaissance ✅ (phase 5, migration 0005)

Implémenté : `entity` (type, nom canonique, `merged_into`), `entity_alias` (origine
EXTRACTOR/HUMAN), `relation` (`relation_key` unique, `qualifier`, `level`, `origin`,
`retracted_at`), `relation_evidence` (observation, document, page, case, extrait),
`correction` (journal : action, avant, après, auteur, motif), `search_document` (texte normalisé,
plongement `vector`, `embedder` ; index GIN plein texte). Rien n'est effacé : fusion = pointeur,
retrait = date.

Détail prévu à l'origine :

| Table | Colonnes clés |
|---|---|
| `entity` | `type` (CHARACTER, EVENT, LOCATION, OBJECT, CONCEPT, SERIES, CONTINUITY, COMIC), nom canonique |
| `entity_alias` | entité, alias, langue |
| `relation` | source, cible, `type` (APPEARS_IN, REFERENCES, CONTRADICTS, PRECEDES, REVEALS, FORESHADOWS, RELATED_TO, OPPOSES), `level`, confiance |
| `correction` | cible, ancienne valeur, nouvelle valeur, auteur, motif, `superseded_by` |
| `embedding` | cible, `model`, `dimension`, `vector` (pgvector, index HNSW) |
| recherche plein texte | colonnes `tsvector` FR et EN générées, index GIN |

Le graphe est stocké en PostgreSQL (`entity` + `relation`, requêtes récursives) — ADR-0003.

## Théories ✅ (phase 7, migration 0007)

`theory` (titre, énoncé, `level` THEORY/SPECULATION — CANON interdit par contrainte —, statut
OPEN/SUPPORTED/CONTESTED/REFUTED, confiance 0–1, documents, sujets, `counter_search_at`),
`theory_evidence` (rôle SUPPORTS/REFUTES, document, page, case, extrait, `verified`, niveau,
note, origine HUMAN/RESEARCHER, auteur, `retracted_at` + motif), `theory_alternative`,
`theory_event` (journal append-only, score résultant dans `detail`).

## Éditorial ✅ (phase 6, migration 0006)

Implémenté : `mission` (type, statut, documents, paramètres, résultat), `mission_task`
(agent, critique, statut, entrées/sorties, tentatives, erreur), `approval_request` (résumé,
recommandation, décision, auteur, commentaire), `agent_run` (fournisseur, modèle, prompt,
jetons, coût, erreur).

## Éditorial et agents — suite 🔜 (phases 7, 10)

`mission`, `mission_task`, `agent_run` (agent, entrées/sorties JSON validées, `prompt_id`,
`prompt_version`, fournisseur, modèle, jetons, coût, latence, erreur), `approval_request`,
`research_dossier`, `script`, `script_version` (langue, contenu, étape), `script_score`
(8 critères + `factual_veto`).

## Marché ✅ (phases 2b, 8, migration 0008)

`market_source` (fiche : type, accès, quota, conditions, classe, langue, configuration,
`verified_at`/`verified_by`), `market_collection` (trace de chaque collecte : statut, paramètres,
unités de quota, erreur), `market_item` (plateforme, identifiant externe unique, titre, langue
fr/en, publication), `market_metric` (views/likes/comments uniquement, `data_class = 'PUBLIC'`,
`observed_at`, append-only), `market_topic` (nom, mots-clés FR/EN).

## Performance 🔜 (phase 11)

`content_item`, `performance_metric` (série temporelle, comptes autorisés uniquement,
`PRIVATE_AUTHORIZED`).

## Voix 🔜 (phase 12)

`voice_session`, `voice_turn` (transcription, réponse, latences), `pronunciation_lexicon`.
