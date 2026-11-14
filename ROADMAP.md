# ROADMAP

Statuts : **NOT IMPLEMENTED** · **IMPLEMENTED** (le code existe) · **TESTED** (tests automatisés
verts) · **VALIDATED** (validé sur cas réels / corpus de référence) · **BLOCKED** (préciser).

## Vue d'ensemble

| Phase | Contenu | Statut | Dépend de |
|---|---|---|---|
| 0 | Audit du dépôt et architecture | VALIDATED | — |
| 1 | Core Platform | TESTED (socle) | 0 |
| 2 | Comic Library | TESTED | 1 |
| 2b | Market Intelligence — collecte (avancée, voir ci-dessous) | NOT IMPLEMENTED | 1 |
| 3 | Comic Vision | TESTED (texte réel : BLOCKED, voir ci-dessous) | 2 |
| 4 | Forensic Intelligence (coût nul) | TESTED | 3 |
| 5 | Knowledge Intelligence | NOT IMPLEMENTED | 4 |
| 6 | Editorial Director (+ banc d'essai voix) | NOT IMPLEMENTED | 5 |
| 7 | Research et Theory Laboratory | NOT IMPLEMENTED | 6 |
| 8 | Market Intelligence — analyse | NOT IMPLEMENTED | 2b, 6 |
| 9 | Social Intelligence | NOT IMPLEMENTED | 8 |
| 10 | Maximum Storytelling | NOT IMPLEMENTED | 6, 7 |
| 11 | Performance Intelligence | NOT IMPLEMENTED | 9, 10 |
| 12 | Adaptive Voice | NOT IMPLEMENTED | 6 |
| 13 | Intégration, sécurité, optimisation, production | NOT IMPLEMENTED | toutes |

### Changements d'ordre (justifiés)

- **Market Intelligence scindée (2b puis 8)** : la collecte est indépendante du corpus de comics
  et l'historique de tendances ne s'accumule qu'avec le temps. La démarrer tôt donne des
  séries temporelles exploitables quand l'analyse arrive en phase 8.
- **Banc d'essai STT/TTS avancé en phase 6** : le choix des fournisseurs vocaux exige une
  comparaison réelle (latence, noms propres FR/EN) ; la mener tôt évite de bloquer la phase 12.

## Phase 1 — Core Platform

| Élément | Statut |
|---|---|
| Monorepo uv + pnpm, conventions, CLAUDE.md | TESTED |
| CI (python, migrations, web, docker), security | TESTED (11 jobs verts sur GitHub, run 43613994469 et 43613996873) ; dependency-review IMPLEMENTED |
| Configuration typée (`primestone.config`) | TESTED |
| Modèle de provenance (`primestone.provenance`) | TESTED |
| Passerelle IA + fournisseur simulé + budget (`primestone.ai_gateway`) | TESTED |
| File de tâches durable PostgreSQL (`primestone.jobs`) | TESTED (concurrence, reprise, nouvelles tentatives) |
| Migration 0001 (pgvector, pipeline_run, pipeline_step) | TESTED (aller-retour + `alembic check`) |
| API FastAPI `/api/v1/health`, `/health/ready` | TESTED |
| Worker (registre de gestionnaires, arrêt propre) | TESTED (y compris en conteneur) |
| Web Next.js (tableau des modules, `/api/health`) | TESTED (lint, types, tests, build) |
| Images Docker api, worker, web | TESTED localement (non-root, sondes de santé OK) |
| Workflows de déploiement staging/production (WIF) | IMPLEMENTED, inactifs (GCP non provisionné) |
| Authentification utilisateur (Identity-Aware Proxy) | NOT IMPLEMENTED |
| Journalisation JSON structurée, traçage | NOT IMPLEMENTED |
| Adaptateurs réels de fournisseurs IA | NOT IMPLEMENTED (après benchmark, phase 3) |

**Critères de validation** : CI verte sur GitHub ; migrations aller-retour ; aucun secret
détecté (gitleaks) ; déploiement staging réussi une fois GCP autorisé.

## Phase 2 — Comic Library

Import (PDF, CBZ) → validation (hash SHA-256, doublons, intégrité, nombre de pages)
→ extraction → rendu des pages (WebP, stockage objet) → statut par page.
Fiche du module : [docs/modules/comic-library.md](docs/modules/comic-library.md).

| Élément | Statut |
|---|---|
| Import par lots (CLI `primestone-library`, API `POST /library/imports`) | TESTED |
| Détection par signature, validation PDF (PDFium) et CBZ (anti-traversée, anti-bombe zip) | TESTED |
| Déduplication SHA-256 (entre lots et dans un même lot) | TESTED |
| Rendu WebP par page, profil versionné (ADR-0009) | TESTED |
| Règle de complétude (pages attendues, page illisible → jamais COMPLETE) | TESTED |
| Reprise après arrêt brutal d'un worker | TESTED |
| Rapport de lot (statuts, pages, volumes, durée) | TESTED |
| Vue « Bibliothèque » dans le web | TESTED |
| Stockage Cloud Storage (adaptateur GCS, URL signées) | NOT IMPLEMENTED — requis avant déploiement |
| Métadonnées ComicInfo.xml (série, numéro) | NOT IMPLEMENTED |
| Validation sur la bibliothèque réelle de l'utilisateur | NOT IMPLEMENTED — passage à VALIDATED |

**Critères** : lot de 50 comics ou plus importé ✅ (60 comics, 1 330 pages, voir mesures) ;
reprise après arrêt forcé sans doublon ni perte ✅ ; une page manquante bloque `COMPLETE` ✅ ;
durée et volumes mesurés ✅. Reste pour VALIDATED : exécution sur de vrais comics.

**Mesures (2026-11-14, 4 vCPU, 4 workers, profil `webp-d2400-q85`)** : 60 comics synthétiques
(1 325×2 050 px, 18 à 26 pages), 67 Mo d'originaux → 1 330 pages rendues en 73,6 s
(≈ 18 pages/s), 0 échec ; ré-import du même lot : 0,25 s, 60 doublons, aucun traitement.
Les pages synthétiques étant presque blanches, le volume rendu (15 Mo) sous-estime fortement
celui de vrais comics (attendu : 0,3 à 0,8 Mo par page).

## Phase 2b — Market Intelligence (collecte)

Connecteurs avec fiche d'accès (quotas, conditions d'utilisation, classe de données) :
YouTube Data API v3 (public), YouTube Analytics (chaîne Primestone, OAuth), Reddit (API
officielle), flux RSS d'actualités comics. Instantanés quotidiens horodatés.

**Critères** : 100 % des données portent une `DataClass` ; aucune source sans fiche validée.

## Phase 3 — Comic Vision

Fiche : [docs/modules/comic-vision.md](docs/modules/comic-vision.md) · ADR-0010.

| Élément | Statut |
|---|---|
| Détection des cases (local, redressement des scans inclinés) | TESTED — F1 = 1,000 sur 200 planches synthétiques |
| Ordre de lecture LTR / RTL | TESTED — 100 % |
| Rattachement des textes aux cases, ordre du texte | TESTED |
| Interface fournisseur + fournisseur simulé | TESTED |
| Adaptateur Claude (transcription, type, langue, locuteur) | IMPLEMENTED — testé avec un client simulé, jamais appelé réellement |
| Estimation, budget, jamais payé deux fois, analyses en ajout seul | TESTED |
| API, CLI `primestone-vision`, visionneuse web avec superposition | TESTED |
| Métriques du banc d'essai (F1 cases, ordre, CER) | TESTED |
| Banc d'essai sur vrais comics (transcription, locuteurs, coût réel) | **BLOCKED** — corpus annoté + budget + clé API à fournir |
| Bulles à cheval sur une gouttière | limite connue (F1 = 0,62) — à traiter si le banc réel le confirme |

**Critères** : précision/rappel des cases ✅ (synthétique) ; CER FR/EN et exactitude des
locuteurs sur corpus réel ⏳ (BLOCKED).

## Phase 4 — Forensic Intelligence (coût nul)

Fiche : [docs/modules/forensic.md](docs/modules/forensic.md) · ADR-0011.

| Élément | Statut |
|---|---|
| Mode zéro coût par défaut (refus des fournisseurs payants avant tout appel) | TESTED |
| Transcription humaine (web + API), versionnée, CANON | TESTED (y compris dans un vrai navigateur) |
| Fournisseur de vision local gratuit (Ollama) | IMPLEMENTED — testé avec serveur simulé, à essayer sur la machine de l'utilisateur |
| Cases détectées à la volée pour transcrire une page jamais analysée | TESTED |
| Extracteurs : texte, répliques, mentions, premières attestations, affirmations, contradictions, variantes de noms | TESTED |
| Discipline CANON / INTERPRETATION, preuves exactes, idempotence, corrections | TESTED |
| Complétude (rapport INCOMPLETE tant qu'une page manque) | TESTED |
| Rapport forensique (CLI, API, web) | TESTED |
| Objets, lieux, symboles, transitions narratives | NOT IMPLEMENTED (nécessitent une analyse visuelle) |
| Validation sur vrais comics transcrits | NOT IMPLEMENTED — passage à VALIDATED |

**Critères** : 100 % des observations ont une preuve résolvable ; catégories jamais mélangées ;
contradictions injectées dans le corpus détectées.

## Phase 5 — Knowledge Intelligence

Entités, alias FR/EN, relations typées avec provenance, corrections versionnées, recherche
hybride (plein texte + pgvector), graphe en PostgreSQL.

**Critères** : relations toutes prouvées ; historique de corrections complet ; requêtes de
graphe et de recherche dans les budgets de latence.

## Phase 6 — Editorial Director

Chief Editor (machine à états persistée), agents spécialisés à contrats typés, demandes
d'approbation humaine. Banc d'essai STT/TTS.

**Critères** : mission de bout en bout sur le corpus ; gestion des échecs d'agents ; aucune
conclusion sans preuve.

## Phase 7 — Research et Theory Laboratory

Théories avec preuves, contre-preuves, alternatives, confiance ; confrontation entre agents.

## Phase 8 — Market Intelligence (analyse)

Sujets populaires, saturation, niches, différences culturelles, score d'écart EN→FR.

## Phase 9 — Social Intelligence

Stratégies YouTube (long), TikTok (découverte), Instagram (Reels, carrousels) ; déclinaisons
autonomes construites depuis l'architecture narrative, pas par découpage mécanique.

## Phase 10 — Maximum Storytelling

Workflow en 13 étapes, notation sur 100, veto factuel, versions FR et EN adaptées.

**Critères** : veto factuel testé ; relecture humaine en aveugle FR/EN au-dessus du seuil.

## Phase 11 — Performance Intelligence

Boucle RESEARCH → CREATE → PUBLISH → MEASURE → LEARN → OPTIMIZE sur les comptes autorisés.
Observations, hypothèses et causalités démontrées strictement distinguées.

## Phase 12 — Adaptive Voice

Streaming, VAD, interruptions, cinq personnalités, lexique de prononciation, mode texte.

**Critères** : latence au premier son mesurée (< 1 s visé) ; interruptions fiables ; mode texte.

## Phase 13 — Production

Revue de sécurité, test de charge, coûts réels vs estimés, restauration de sauvegarde testée,
intégrations Panel Explorer et Motion Studio (API facultatives).
