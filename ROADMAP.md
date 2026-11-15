# ROADMAP

Statuts : **NOT IMPLEMENTED** · **IMPLEMENTED** (le code existe) · **TESTED** (tests automatisés
verts) · **VALIDATED** (validé sur cas réels / corpus de référence) · **BLOCKED** (préciser).

## Vue d'ensemble

| Phase | Contenu | Statut | Dépend de |
|---|---|---|---|
| 0 | Audit du dépôt et architecture | VALIDATED | — |
| 1 | Core Platform | TESTED (socle) | 0 |
| 2 | Comic Library | TESTED | 1 |
| 2b | Market Intelligence — collecte (avancée, voir ci-dessous) | TESTED (livrée avec la phase 8 ; collecte réelle BLOCKED) | 1 |
| 3 | Comic Vision | TESTED (texte réel : BLOCKED, voir ci-dessous) | 2 |
| 4 | Forensic Intelligence (coût nul) | TESTED | 3 |
| 5 | Knowledge Intelligence (coût nul) | TESTED | 4 |
| 6 | Editorial Director (coût nul) | TESTED (banc voix : BLOCKED) | 5 |
| 7 | Research et Theory Laboratory (coût nul) | TESTED | 6 |
| 8 | Market Intelligence — analyse (coût nul) | TESTED | 2b, 6 |
| 9 | Social Intelligence (coût nul) | TESTED | 8 |
| 10 | Maximum Storytelling (coût nul) | TESTED | 6, 7 |
| 11 | Performance Intelligence (coût nul) | TESTED | 9, 10 |
| 12 | Adaptive Voice (coût nul) | TESTED (banc réel BLOCKED) | 6 |
| 13 | Intégration, sécurité, optimisation, production | IMPLEMENTED (déploiement BLOCKED : accord du propriétaire) | toutes |
| 14 | Mesure par objectif & expérimentation scientifique (coût nul) | TESTED (données réelles : OAuth du propriétaire) | 11 |
| 15 | Audience Intelligence & communauté (coût nul) | TESTED (données réelles : clé et OAuth du propriétaire) | 5, 8, 11, 14 |
| 16 | Content Opportunity Engine (coût nul) | TESTED | 7, 8, 15 |
| 17 | Audience Bridge, architectures narratives, multi-plateforme FR/EN (coût nul) | TESTED | 9, 10, 15 |
| 18 | Packaging, marque, séries & franchises (coût nul) | TESTED (charte réelle : à fournir par le propriétaire) | 14, 15, 17 |
| 19 | Content Performance Lab & validation finale (coût nul) | TESTED — validation réelle : 0/13 tant que les données réelles manquent | 14, 18 |
| 20 | Marque et gouvernance (coût nul) | TESTED (piliers et charte réels : à approuver par le fondateur) | 18 |
| 21 | Moteur d'émissions (shows, formats, cycle de vie) *(proposée)* | NOT IMPLEMENTED — en attente de validation | 20 |
| 22 | Identité indépendante (voix, visuels, langues) *(proposée)* | NOT IMPLEMENTED — en attente de validation | 20, 21 |
| 23 | Distribution et portefeuille *(proposée)* | NOT IMPLEMENTED — en attente de validation | 21 |
| 24 | Droits, mémoire éditoriale, coûts *(proposée)* | NOT IMPLEMENTED — en attente de validation | 20 à 23 |

Décision stratégique « PRIMESTONE, média autonome » (le fondateur est directeur éditorial,
pas présentateur) : audit et architecture réconciliée dans
[docs/audit/autonomous-media-brand.md](docs/audit/autonomous-media-brand.md).

Extension validée par le propriétaire le 2026-11-15 (« je valide tout »). Analyse des dépendances et
justification de l'ordre dans [docs/audit/extension-audience-growth.md](docs/audit/extension-audience-growth.md).
La plateforme n'est **complète** qu'une fois les 13 critères de validation de l'extension
démontrés sur données réelles.

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
| Authentification utilisateur (Identity-Aware Proxy) | TESTED côté application (vérification du jeton, phase 13) ; IAP lui-même à provisionner |
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
| Validation sur la bibliothèque réelle de l'utilisateur | EN COURS — 3 vrais numéros (79 pages) importés et rendus sans erreur ; lot de 50 réels à faire |

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

**Critères** : 100 % des données portent une `DataClass` ✅ (contrainte en base) ; aucune source
sans fiche validée ✅. Livrée avec la phase 8, voir ci-dessous.

| Élément | Statut |
|---|---|
| Sources avec fiche (accès, quota, conditions), validation humaine obligatoire | TESTED |
| YouTube Data API v3 (gratuite, quota contrôlé, clé jamais divulguée) | IMPLEMENTED — testé avec API simulée |
| Flux RSS / Atom (HTTPS, DOCTYPE refusé) | IMPLEMENTED — testé hors ligne |
| Import manuel CSV / API (métriques privées refusées) | TESTED |
| Instantanés horodatés, append-only, idempotents ; `snapshot` quotidien | TESTED (planification : cron local ; Cloud Scheduler en phase 13) |
| YouTube Analytics (chaîne Primestone, OAuth) | NOT IMPLEMENTED — phase 11 |
| Reddit | NOT IMPLEMENTED — application OAuth approuvée exigée |
| Collecte réelle | **BLOCKED** — clé YouTube gratuite à créer par le propriétaire + hôtes réseau à autoriser |

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

## Phase 5 — Knowledge Intelligence (coût nul)

Fiche : [docs/modules/knowledge.md](docs/modules/knowledge.md) · ADR-0012.

| Élément | Statut |
|---|---|
| Entités (personnages, comics, séries) et alias FR/EN | TESTED |
| Relations typées dérivées des observations, preuve obligatoire | TESTED |
| Corrections journalisées (renommage, alias, fusion, retrait, relation manuelle) | TESTED (y compris dans un navigateur) |
| Reconstruction idempotente qui respecte les corrections | TESTED |
| Graphe : voisinage et plus court chemin (CTE récursives) | TESTED |
| Recherche hybride plein texte + vecteurs (RRF), versions servies uniquement | TESTED |
| Plongements sémantiques locaux (Ollama) | IMPLEMENTED — testé avec serveur simulé |
| Lieux, objets, événements, ordre de publication automatique | NOT IMPLEMENTED |
| Validation sur la bibliothèque réelle | NOT IMPLEMENTED — passage à VALIDATED |

**Critères** : relations toutes prouvées ; historique de corrections complet ; requêtes de
graphe et de recherche dans les budgets de latence.

## Phase 6 — Editorial Director (coût nul)

Fiche : [docs/modules/editorial.md](docs/modules/editorial.md) · ADR-0013.

| Élément | Statut |
|---|---|
| Chief Editor : missions durables, reprise après interruption | TESTED |
| Agents : Research Director, Comics Analyst, Continuity Editor, Character Researcher, Fact Checker | TESTED |
| Gestion des échecs (2 tentatives, dégradé vs critique) | TESTED |
| Confrontation des résultats et recommandation | TESTED |
| Fact Checker bloquant (citations, âges contredits, références) | TESTED |
| Approbation humaine (refusée si erreur majeure) | TESTED (y compris navigateur + vrai worker) |
| Rédaction par modèle local gratuit, retenue seulement si vérifiée | IMPLEMENTED — testé avec modèle simulé |
| Agents des phases 7 à 11 | TESTED (livrés) ; seul le Visual Analyst attend un modèle de vision |
| Banc d'essai STT/TTS | **BLOCKED** — gratuit possible en local (whisper.cpp, Piper) mais exige de télécharger des modèles : à faire sur la machine de l'utilisateur, phase 12 |

**Critères** : mission de bout en bout ✅ ; gestion des échecs ✅ ; aucune conclusion sans
preuve ✅ (Fact Checker sur chaque livrable).

## Phase 7 — Research et Theory Laboratory (coût nul)

Fiche : [docs/modules/lab.md](docs/modules/lab.md) · ADR-0014.

| Élément | Statut |
|---|---|
| Théories structurées (énoncé, sujets, documents), jamais CANON (contrainte en base) | TESTED |
| Preuves et contre-preuves vérifiées sur la transcription, retrait motivé, revérification | TESTED |
| Alternatives, journal append-only | TESTED |
| Niveau / statut / confiance calculés et expliqués (`lab-confidence@1`) | TESTED |
| Theory Researcher (candidats pour/contre, gratuit) ; classement humain | TESTED |
| Missions THEORY_REVIEW et RESEARCH_DOSSIER (Fact Checker bloquant) | TESTED |
| API, CLI `primestone-lab`, pages web `/lab` | TESTED (web : lint, types, build) |
| Validation sur la bibliothèque réelle | NOT IMPLEMENTED — passage à VALIDATED |

**Critères** : aucune théorie sans preuve vérifiable ✅ ; contre-preuves cherchées avant THEORY
✅ ; confiance explicable ✅.

## Phase 8 — Market Intelligence (analyse, coût nul)

Fiche : [docs/modules/market.md](docs/modules/market.md) · ADR-0015.

| Élément | Statut |
|---|---|
| Sujets (mots-clés FR/EN) et correspondance par mots | TESTED |
| Score d'écart EN→FR, saturation, popularité, niches, différences culturelles (`market-gap@1`) | TESTED |
| Refus de chiffrer sous le seuil de données (INSUFFICIENT_DATA) | TESTED |
| Résultats ESTIMATE reliés à leurs sources PUBLIC | TESTED |
| Agent Market Analyst + mission MARKET_BRIEF du Chief Editor | TESTED |
| API `/market/*`, CLI `primestone-market`, page web `/market` | TESTED (navigateur, mobile) |
| Validation sur données réelles | NOT IMPLEMENTED — exige la collecte réelle (2b) |

**Critères** : aucune métrique privée de concurrent ✅ (contrainte en base) ; aucun chiffre
sans données suffisantes ✅ ; chaque score explicable ✅.

## Phase 9 — Social Intelligence (coût nul)

Fiche : [docs/modules/social.md](docs/modules/social.md) · ADR-0016.

| Élément | Statut |
|---|---|
| Content Strategist : faits vérifiés → rôle narratif et section | TESTED |
| YouTube long (chapitres), TikTok, Reels (autre angle), carrousel (≤ 20 cartes) | TESTED |
| Mission SOCIAL_PACKAGE (livrable approuvé seulement, Fact Checker, approbation) | TESTED |
| Formats datés et sourcés, à revérifier | IMPLEMENTED — sources non consultables depuis ce conteneur |
| API, CLI `primestone-editorial social`, bouton web | TESTED (web : lint, types, build) |
| Scripts rédigés (hooks, voix) | NOT IMPLEMENTED — phase 10 |

**Critères** : aucun fait non vérifié dans une déclinaison ✅ ; structures distinctes par
plateforme ✅.

## Phase 10 — Maximum Storytelling (coût nul)

Fiche : [docs/modules/storytelling.md](docs/modules/storytelling.md) · ADR-0017.

| Élément | Statut |
|---|---|
| Scripts FR/EN, 13 étapes (retour possible), versions append-only, journal | TESTED |
| Import .md / .txt / .pdf (ordre de lecture, testé sur un vrai script) | TESTED |
| Sections horodatées (points et plages), durée estimée | TESTED |
| Citations par page (Fact Checker) et par œuvre (bibliothèque / à sourcer) | TESTED |
| Pré-notation sur 100, 8 critères expliqués (`script-score@1`) | TESTED — heuristique |
| Veto factuel absolu (service, approbation, validation finale) | TESTED |
| Adaptation FR/EN reliée | TESTED |
| Agents Story Architect, Editorial Critic ; mission SCRIPT_REVIEW | TESTED |
| API `/scripts`, CLI `primestone-script`, pages web `/scripts` | TESTED (web : lint, types, build) |
| Relecture humaine en aveugle FR/EN au-dessus du seuil | NOT IMPLEMENTED — à faire par le propriétaire |

**Critères** : veto factuel testé ✅ ; relecture humaine en aveugle : à faire (calibrage).

## Phase 11 — Performance Intelligence (coût nul)

Fiche : [docs/modules/performance.md](docs/modules/performance.md) · ADR-0018.

| Élément | Statut |
|---|---|
| Contenus Primestone + métriques PRIVATE_AUTHORIZED (contrainte en base), append-only | TESTED |
| Import CSV YouTube Studio (FR/EN, colonnes inconnues signalées) | TESTED |
| Client YouTube Analytics API v2 (OAuth, lecture seule) | IMPLEMENTED — testé avec API simulée ; connexion réelle BLOCKED (OAuth du propriétaire) |
| Liaison vidéo ↔ script noté ; repères et signaux Spearman (`perf-learn@1`) | TESTED |
| Agent Performance Analyst, mission PERFORMANCE_REVIEW | TESTED |
| API `/performance`, CLI `primestone-performance`, page web `/performance` | TESTED (web : lint, types, build) |
| Validation sur la vraie chaîne | NOT IMPLEMENTED — exige un export Studio réel |

## Phase 12 — Adaptive Voice (coût nul)

Fiche : [docs/modules/voice.md](docs/modules/voice.md) · ADR-0019.

| Élément | Statut |
|---|---|
| Interfaces STT/TTS + fournisseurs simulés | TESTED |
| Adaptateurs locaux gratuits whisper.cpp et Piper (HTTP) | IMPLEMENTED — testés avec serveurs simulés |
| Réponses ancrées (recherche hybride), citées, vérifiées avant d'être dites ; refus sans source | TESTED |
| 5 personnalités ; hypothèses seulement en Brainstorming, annoncées | TESTED |
| WebSocket : texte ou WAV, phrases synthétisées une à une, interruption | TESTED |
| Page web `/voice` : micro (WAV 16 kHz), lecture en file, interruption, mode texte | TESTED (mode texte en navigateur ; micro non testable en CI) |
| Banc STT/TTS réel (latence, noms propres FR/EN) | **BLOCKED** — modèles locaux à installer par le propriétaire |

## Phase 13 — Production

ADR-0020 · checklist : [docs/operations/production-checklist.md](docs/operations/production-checklist.md).

| Élément | Statut |
|---|---|
| Vérification IAP dans l'API (ES256, audience, expiration ; HTTP + WebSocket) | TESTED |
| Stockage GCS sans clé (jeton du serveur de métadonnées), copies en flux | TESTED (API simulée) |
| Configuration cloud stricte (bucket, audience IAP, fournisseurs réels obligatoires) | TESTED |
| API d'intégration Panel Explorer / Motion Studio (contrat 1.0, scripts validés seulement) | TESTED |
| En-têtes de sécurité web | TESTED (vérifiés sur le serveur) ; CSP à nonces : NOT IMPLEMENTED |
| PDFium sérialisé (segfault de concurrence corrigé) | TESTED |
| Workflows de déploiement : variables cloud exigées et transmises | IMPLEMENTED, inactifs |
| Provisionnement GCP, test de charge, coûts réels, restauration de sauvegarde | **BLOCKED** — ressources payantes : accord explicite du propriétaire requis |

## Phase 14 — Mesure par objectif & expérimentation (coût nul)

ADR-0021 · fiche : [docs/modules/performance.md](docs/modules/performance.md#phase-14--mesure-par-objectif-et-expériences-adr-0021).

| Élément | Statut |
|---|---|
| Objectif et format par contenu ; évaluation par objectif face aux pairs (`objective-kpi@1`) | TESTED |
| Métriques élargies et segments agrégés, jamais estimés | TESTED |
| Courbes de rétention (YouTube Analytics) | TESTED (API simulée) |
| Expériences : hypothèse → variantes → verdict statistique (`ab-proportion@1`), pas de gagnant sans échantillon suffisant | TESTED |
| Niveaux de preuve OBSERVED / HYPOTHESIS / DEMONSTRATED | TESTED |
| OAuth « application installée » (loopback), synchronisation de la chaîne | IMPLEMENTED — autorisation réelle : action du propriétaire |
| API, CLI, page `/performance` (objectifs, expériences) | TESTED |

## Phase 15 — Audience Intelligence & communauté (coût nul)

ADR-0022 · fiche : [docs/modules/audience.md](docs/modules/audience.md).

| Élément | Statut |
|---|---|
| Segments par motivations et niveau (âge refusé) ; statut calculé HYPOTHESIS / CONFIRMED | TESTED |
| Preuves d'audience (METRIC, COMMENT_CLUSTER, MARKET, DECLARED), retrait et recalcul | TESTED |
| Graphe d'audience relié au graphe de connaissances et aux sujets, arêtes prouvées | TESTED |
| Commentaires publics de la chaîne, identité des auteurs jamais conservée | TESTED (API simulée) |
| Classement, récurrences, propositions (sans interaction automatisée) | TESTED |
| Agent Audience Analyst, mission AUDIENCE_BRIEF ; API, CLI, page `/audience` | TESTED |

## Phase 16 — Content Opportunity Engine (coût nul)

ADR-0023 · fiche : [docs/modules/market.md](docs/modules/market.md#phase-16--opportunités-éditoriales-adr-0023).

| Élément | Statut |
|---|---|
| Signaux croisés : marché, communauté, audiences, pages transcrites, théories | TESTED |
| Score `opportunity@1` sur critères mesurés seulement, confiance, critères manquants listés | TESTED |
| Popularité EN ≠ demande FR : HYPOTHESIS sans demande FR observée | TESTED |
| Fiche complète (public, besoin, angle, preuves, concurrence, risques, formats, recommandation) | TESTED |
| Mission OPPORTUNITY_BRIEF, API `/market/opportunities`, CLI, section web | TESTED |
| Compatibilité avec l'identité Primestone | NOT IMPLEMENTED — phase 18 (charte, séries) |

## Phase 17 — Audience Bridge, architectures, rétention, multi-plateforme (coût nul)

ADR-0024 · fiches : [storytelling](docs/modules/storytelling.md#phase-17--niveaux-architectures-rétention-adr-0024), [social](docs/modules/social.md#phase-17--nouveaux-formats).

| Élément | Statut |
|---|---|
| Niveaux DISCOVERY / EXPLORATION / EXPERTISE, variantes reliées, contrôles par niveau, veto identique | TESTED |
| Bibliothèque de techniques et 6 architectures (principes seulement), plans avec faits mot pour mot | TESTED |
| Rétention du script (longueurs, transitions, répétitions, révélations, visuels) + décrochages réels | TESTED |
| Motion Studio contrat 1.1 (intentions par section) | TESTED |
| Shorts, publication communautaire, podcast, dossier écrit | TESTED |
| Adaptation FR/EN culturelle (réécriture humaine reliée) | TESTED (phase 10) ; rédaction assistée : NOT IMPLEMENTED |

## Phase 18 — Packaging, marque, séries & franchises (coût nul)

ADR-0025 · fiche : [docs/modules/creative.md](docs/modules/creative.md).

| Élément | Statut |
|---|---|
| 10 titres, 5 miniatures, 3 promesses, 3 accroches depuis les faits vérifiés | TESTED |
| Honnêteté (promesse tenue, termes bannis), lisibilité, adéquation au niveau | TESTED |
| Aucune prédiction de CTR ; tests proposés reliés aux expériences | TESTED |
| Charte de marque versionnée, contrôles de miniatures | TESTED (charte par défaut à personnaliser) |
| Séries et franchises : promesse, identité, structure, durée, cohérence des épisodes | TESTED |
| Agent Brand & Packaging Editor, mission PACKAGING_REVIEW ; API, CLI, pages web | TESTED |
| Titres proposés par modèle local | IMPLEMENTED (facultatif, mêmes contrôles) |

## Phase 19 — Content Performance Lab & validation finale (coût nul)

ADR-0026 · fiche : [docs/modules/performance.md](docs/modules/performance.md#phase-19--content-performance-lab-adr-0026).

| Élément | Statut |
|---|---|
| Boucle RESEARCH → … → OPTIMIZE suivie par sujet | TESTED |
| Video Autopsy (OBSERVED / HYPOTHESIS / DEMONSTRATED, manques listés) | TESTED |
| Hook Laboratory, Drop-off Analysis, Returning Audience | TESTED (NON FOURNI / INSUFFISANT sans données) |
| Mission VIDEO_AUTOPSY ; API `/performance/lab/*` ; CLI ; validation sur `/performance` | TESTED |
| **13 critères de complétude de l'extension** | **NOT YET (0/13 en base vide)** : à démontrer sur données réelles (`primestone-performance validation`) |

## Phase 20 — Marque et gouvernance (coût nul)

ADR-0027 · fiche : [docs/modules/governance.md](docs/modules/governance.md).

| Élément | Statut |
|---|---|
| `media_brand` PRIMESTONE (FR principal, EN), `brand_id` sur séries, scripts, contenus, missions, expériences, chartes | TESTED (migration 0015 réversible) |
| Piliers éditoriaux, politiques par action, journal des décisions | TESTED |
| Approbation, rejet, annulation réservés au fondateur ; agents refusés côté serveur | TESTED |
| Annulation exacte (état antérieur mémorisé) | TESTED |
| Charte : brouillon soumis, seule la version approuvée s'applique | TESTED |
| API `/governance/*`, CLI `primestone-brand`, page `/governance` | TESTED |

