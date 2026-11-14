# COSTS

> Ordres de grandeur **à valider avec les tarifs en vigueur** au moment du provisionnement.
> Aucune ressource n'est créée sans approbation explicite. Les coûts réels mesurés remplaceront
> ces estimations (phase 13).

## Stratégie (usage personnel)

- **Un seul environnement cloud au départ** : `staging` sert d'environnement personnel. Le projet
  `production` n'est créé que lorsque l'usage le justifie (économise une instance Cloud SQL).
- Mise à l'échelle à zéro de tous les services Cloud Run.
- Cloud SQL : plus petite configuration compatible, arrêtable hors usage.
- Budget GCP avec alertes à 50 %, 90 % et 100 %.
- Garde-fou applicatif : `PRIMESTONE_AI_BUDGET_PER_MISSION_USD` (défaut 5 USD) — l'`AIGateway`
  refuse tout appel qui ferait dépasser le budget.
- Estimation affichée avant tout lot ; approbation humaine au-delà du seuil.
- Aucun appel payant en CI.

## Infrastructure (mensuel, un environnement)

| Poste | Estimation | Leviers |
|---|---|---|
| Cloud SQL PostgreSQL (cœur partagé) | ≈ 10–30 USD | arrêt hors usage, taille minimale |
| Cloud Run (web, api, worker) | ≈ 0–10 USD | min-instances 0 |
| Cloud Storage (PDF + pages rendues) | < 5 USD pour ~100 Go | WebP, cycle de vie |
| Artifact Registry | < 2 USD | nettoyage des anciennes images |
| Secret Manager, Logging, Monitoring | ≈ 0–5 USD | rétention des logs courte |

## IA (variable, principal poste)

| Traitement | Unité | Estimation pour un lot de 50 comics (~1 200 pages) |
|---|---|---|
| OCR | page | ≈ 2 USD |
| Analyse visuelle par LLM multimodal | page × passe | ≈ 10–100 USD selon modèle et nombre de passes |
| Embeddings | jeton | < 1 USD |
| Scripts (13 étapes, FR + EN) | script | ≈ 0,5–5 USD |
| STT / TTS | minute | à mesurer lors du banc d'essai (phase 6) |

Leviers : modèle léger pour le tri, modèle fort seulement pour les cases riches ; cache par
`(sha256, page, prompt_version)` pour ne jamais repayer une analyse identique ; traitement
par lots asynchrones des fournisseurs quand disponible.

## Suivi

Chaque `agent_run` enregistre jetons et coût ; tableau de bord par mission, par lot, par
module et par mois (phase 6). Comparaison mensuelle estimation / réel consignée ici.
