# Architecture Decision Records

Format : contexte → décision → alternatives → conséquences. Un ADR accepté n'est pas modifié :
on le remplace par un nouvel ADR (statut « Remplacé par ADR-XXXX »).

| ADR | Titre | Statut |
|---|---|---|
| [0001](0001-modular-monorepo.md) | Monolithe modulaire en monorepo | Accepté |
| [0002](0002-technology-stack.md) | Stack technique | Accepté |
| [0003](0003-postgresql-pgvector-graph.md) | PostgreSQL + pgvector, graphe en relationnel | Accepté |
| [0004](0004-durable-job-queue.md) | File de tâches durable sur PostgreSQL | Accepté |
| [0005](0005-ai-gateway.md) | Passerelle IA indépendante des fournisseurs | Accepté |
| [0006](0006-gcp-region-and-services.md) | GCP europe-west1 et services managés | Accepté |
| [0007](0007-workload-identity-federation.md) | GitHub → GCP par Workload Identity Federation | Accepté |
| [0008](0008-git-workflow.md) | Développement trunk-based | Accepté |

Modèle : [template.md](template.md).
