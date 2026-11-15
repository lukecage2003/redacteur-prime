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
| [0009](0009-content-addressed-storage.md) | Stockage adressé par contenu, profils de rendu versionnés | Accepté |
| [0010](0010-comic-vision.md) | Comic Vision : cases en local, texte par fournisseur IA sous budget | Accepté |
| [0011](0011-zero-cost-forensic.md) | Mode zéro coût et forensique par règles déterministes | Accepté |
| [0012](0012-knowledge-graph.md) | Graphe dérivé des preuves, corrections journalisées, recherche gratuite | Accepté |
| [0013](0013-editorial-director.md) | Editorial Director : missions durables, agents déterministes, Fact Checker bloquant | Accepté |
| [0014](0014-theory-laboratory.md) | Laboratoire des théories : preuves vérifiées, confiance calculée, jamais CANON | Accepté |
| [0015](0015-market-intelligence.md) | Market Intelligence : données publiques gratuites, fiche validée, score explicite | Accepté |
| [0016](0016-social-intelligence.md) | Social Intelligence : déclinaisons depuis les faits vérifiés d'un livrable approuvé | Accepté |
| [0017](0017-storytelling.md) | Maximum Storytelling : scripts en 13 étapes, pré-notation explicable, veto factuel | Accepté |
| [0018](0018-performance.md) | Performance Intelligence : chaîne Primestone uniquement, import gratuit, signaux prudents | Accepté |
| [0019](0019-adaptive-voice.md) | Adaptive Voice : fournisseurs locaux gratuits, réponses ancrées et vérifiées | Accepté |
| [0020](0020-production-readiness.md) | Préparation à la production : IAP vérifié, GCS sans clé, intégrations, PDFium sérialisé | Accepté |
| [0021](0021-measurement-experiments.md) | Mesure par objectif, expériences rigoureuses, OAuth de la chaîne | Accepté |
| [0022](0022-audience-intelligence.md) | Audience Intelligence : segments prouvés, graphe d'audience distinct, communauté anonyme | Accepté |
| [0023](0023-opportunity-engine.md) | Content Opportunity Engine : critères mesurés seulement, demande FR observée exigée | Accepté |
| [0024](0024-audience-bridge-creative.md) | Audience Bridge, architectures narratives, rétention du script, multi-plateforme | Accepté |

Modèle : [template.md](template.md).
