# ADR-0003 — PostgreSQL + pgvector, graphe en relationnel

- Statut : Accepté
- Date : 2026-11-14

## Contexte

Besoins : relationnel (bibliothèque, provenance), plein texte FR/EN, recherche vectorielle,
graphe de connaissances (entités et relations typées avec provenance).

## Décision

Une seule base PostgreSQL 16 (Cloud SQL) avec pgvector. Le graphe est modélisé par les tables
`entity` et `relation` et interrogé en SQL (CTE récursives). Plein texte via `tsvector`
(configurations `french` et `english`). Index vectoriels HNSW.

## Alternatives considérées

- **Neo4j** ou base graphe dédiée : un service de plus à payer, sauvegarder et synchroniser ;
  la provenance et les transactions deviennent distribuées.
- **Base vectorielle dédiée** (Pinecone, Qdrant…) : idem ; pgvector suffit à l'échelle
  d'une bibliothèque personnelle (de l'ordre de 10⁵ à 10⁶ vecteurs).

## Conséquences

Sauvegarde, transactions et provenance au même endroit. Si les parcours de graphe profonds
deviennent un goulot mesuré, un moteur graphe pourra être ajouté en lecture seule (nouvel ADR).
