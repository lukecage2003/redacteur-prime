# ARCHITECTURE

Décisions détaillées : [docs/adr/](docs/adr/). Modules : [docs/modules/](docs/modules/).

## Principes

1. **Monolithe modulaire** (ADR-0001) : un seul code métier (`packages/primestone`), trois points
   d'entrée (API, worker, web). Un module n'est extrait en service que si la charge, la sécurité
   ou l'exploitation le justifient, mesures à l'appui.
2. **Provenance d'abord** : toute affirmation sur une œuvre porte une référence documentaire
   exacte et un niveau d'évidence.
3. **Indépendance des fournisseurs IA** (ADR-0005) : le métier ne connaît que `AIGateway`.
4. **Durabilité** (ADR-0004) : tout traitement long est découpé en étapes idempotentes,
   persistées, reprenables.
5. **Coût maîtrisé** : budget par mission, estimation avant les lots, approbation humaine.

## Vue d'ensemble

```
                  ┌───────────────── Navigateur ─────────────────┐
                  │  Next.js (web)      micro / audio (voix)     │
                  └──────┬───────────────────────┬───────────────┘
                         │ HTTPS                 │ WebSocket
                ┌────────▼─────────┐     ┌───────▼────────┐
                │  Cloud Run: web  │     │ Cloud Run: api │  /api/v1 + WS
                └──────────────────┘     └───┬────────┬───┘
                                             │        │ enfile
                       ┌─────────────────────┘        ▼
                       │                    ┌───────────────────┐
                       │                    │ pipeline_step     │ (PostgreSQL)
                       │                    └────────┬──────────┘
                       │                             │ réserve (SKIP LOCKED)
                       │                   ┌─────────▼──────────┐
                       │                   │ Worker (Cloud Run  │
                       │                   │ worker pool / Jobs)│
                       │                   └───┬──────────┬─────┘
              ┌────────▼────────┐              │          │
              │ Cloud SQL       │◄─────────────┘          │
              │ PG16 + pgvector │                         │
              └─────────────────┘           ┌─────────────▼─────────────┐
              ┌─────────────────┐           │ AIGateway → adaptateurs   │
              │ Cloud Storage   │◄──────────┤ LLM · vision · OCR · STT  │
              │ PDF, pages, médias          │ TTS · embeddings          │
              └─────────────────┘           └───────────────────────────┘
```

## Code

```
packages/primestone/src/primestone/
  config.py        configuration typée (PRIMESTONE_*)
  provenance.py    EvidenceLevel, DataClass, DocumentRef, Observation, Theory, complétude
  ai_gateway/      contrats, registre, budget, traçabilité, fournisseur simulé
  jobs/            file durable PostgreSQL
  db/              moteur, schéma (source de vérité pour `alembic check`)
  comic/ forensic/ knowledge/ editorial/ market/ social/
  storytelling/ performance/ voice/        ← créés phase par phase
apps/api/          FastAPI (routes minces → services de primestone)
apps/worker/       registre de gestionnaires d'étapes, boucle, arrêt propre
apps/web/          Next.js App Router, TypeScript strict, Tailwind
```

Règle de dépendance : `apps/*` → `primestone` ; dans `primestone`, les modules métier
dépendent de `provenance`, `ai_gateway`, `jobs`, `db`, jamais l'inverse. Un module métier
n'importe un autre module métier que via son interface publique (`__init__`).

## Pipeline Comic Library / Forensic

```
IMPORT → VALIDATION → EXTRACTION → RENDU → OCR → CASES → ANALYSE VISUELLE
       → ANALYSE NARRATIVE → VÉRIFICATION → INDEXATION → KNOWLEDGE GRAPH
```

Chaque flèche est une étape `pipeline_step` par document ou par page, avec une clé
d'idempotence `{document_sha256}:{page}:{étape}:{version_pipeline}`. Une nouvelle version
de pipeline ou de prompt produit de nouveaux résultats sans écraser les anciens.

## Multi-agents (Phase 6)

- **Chief Editor** : machine à états persistée (`mission`, `mission_task`), pas une boucle en
  mémoire. Il planifie, délègue, confronte, vérifie les preuves, détecte les contradictions,
  hiérarchise et ouvre des `approval_request`.
- **Agents** (Research Director, Comics Analyst, Visual Analyst, Continuity Editor, Theory
  Researcher, Fact Checker, Content Strategist, Market Analyst, Story Architect, Editorial
  Critic, Performance Analyst) : contrat Pydantic d'entrée/sortie, prompt versionné, outils
  autorisés, budget, limites explicites (ex. le Theory Researcher ne peut pas écrire en CANON).
- **L5 supervisé** : exécution autonome ; approbation humaine pour publication, traitements au-delà
  du seuil de coût, modification du canon, validation finale des scripts.
- Orchestrateur interne léger (ADR à rédiger en phase 6, LangGraph réévalué à ce moment).

## Voix (Phase 12)

```
Micro → VAD client → WebSocket → STT streaming → détection de fin de tour
      → Chief Editor (LLM streaming, personnalité) → découpage en phrases
      → TTS streaming → WebSocket → lecture ; interruption = arrêt immédiat du TTS
```

Fournisseurs STT/TTS interchangeables derrière `ai_gateway`, choisis après banc d'essai.
Personnalités : Conversation, Research, Editorial, Director, Brainstorming. Mode texte de secours.

## Market Intelligence

Connecteurs avec fiche (accès, quotas, conditions, `DataClass`) ; instantanés horodatés ;
score d'écart EN→FR = demande anglophone mesurée × (1 − saturation francophone).
Aucune métrique privée de concurrent n'est estimée et présentée comme un fait.

## Storytelling

Machine à états en 13 étapes (Brief → … → Validation finale), retour possible à n'importe quelle
étape. Notation sur 100 (Hook 15, Architecture 15, Rétention 15, Écriture 15, Originalité 10,
Oralité 10, Exactitude 15, Conclusion 5) et **veto factuel**. FR et EN partagent le dossier de
recherche mais ont chacun leurs angles, hooks et références culturelles.

## GCP

Voir [docs/architecture/gcp.md](docs/architecture/gcp.md) et
[docs/operations/workload-identity-federation.md](docs/operations/workload-identity-federation.md).

## Intégrations Primestone

Panel Explorer et Motion Studio consomment des API dédiées (`/api/v1/integrations/...`),
facultatives : Editorial fonctionne sans elles.
