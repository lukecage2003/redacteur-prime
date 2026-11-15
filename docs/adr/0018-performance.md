# ADR-0018 — Performance Intelligence : chaîne Primestone uniquement, import gratuit, signaux prudents

- Statut : Accepté
- Date : 2026-11-14

## Décision

1. **Périmètre** : `content_item` ne contient que les contenus publiés par Primestone. Leurs
   métriques privées (CTR, rétention, impressions…) sont de classe `PRIVATE_AUTHORIZED`,
   imposée par une contrainte en base. Les concurrents restent dans Market Intelligence, sous
   la contrainte inverse (métriques publiques seulement, ADR-0015).
2. **Entrées gratuites** :
   - export CSV de YouTube Studio : aucun accès API ; en-têtes FR/EN reconnus ; colonnes
     inconnues ignorées et signalées, jamais devinées ; ligne « Total » écartée ;
   - client YouTube Analytics API v2 (`channel==MINE`, lecture seule) : le jeton OAuth est
     injecté et n'apparaît jamais dans les erreurs.
3. **Instantanés** append-only (`performance_metric`), avec période et source.
4. **Boucle `perf-learn@1`** :
   - repères de la chaîne (médianes) et position de chaque vidéo ;
   - corrélation de Spearman entre chaque critère de la note du script (ADR-0017) et la
     rétention ou le CTR, à partir de 5 vidéos reliées à un script noté (sinon
     INSUFFICIENT_DATA) ;
   - recommandations seulement si |rho| ≥ 0,5, toujours formulées comme des signaux, pas des
     preuves.
5. **Agent Performance Analyst**, mission `PERFORMANCE_REVIEW`.

## Conséquences

- La boucle mesurer → apprendre → optimiser relie enfin les notes des scripts aux résultats
  réels. Avec peu de vidéos, elle reste prudente.
- Connexion OAuth réelle : à faire par le propriétaire (BLOCKED). L'export CSV suffit.
