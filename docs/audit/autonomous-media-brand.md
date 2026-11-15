# Décision stratégique « PRIMESTONE, média autonome » : audit et architecture réconciliée

- Date : 2026-11-15
- Statut : **PROPOSITION, en attente de validation du fondateur.** Aucun changement de
  structure avant validation.

## 1. Conclusion de l'audit

La plateforme est déjà organisée autour d'un **Chief Editor** qui orchestre des agents
spécialisés, avec preuves, approbations et traçabilité. Aucune de ses fonctions ne suppose
que le fondateur apparaisse à l'écran ou enregistre sa voix.

Les manques sont surtout **institutionnels** :
- l'entité « marque » n'existe pas : tout est implicitement mono-marque ;
- une émission est une « série » sans cycle de vie complet ;
- la gouvernance (politiques, journal des décisions) se limite aux approbations de missions ;
- la distribution, les droits, la mémoire éditoriale et les coûts ne sont pas modélisés.

Il faut **étendre**, pas reconstruire : 8 tables nouvelles, 6 tables existantes enrichies par
des colonnes facultatives. Aucune suppression, aucun renommage.

## 2. Capacités logiques : existant, partiel, manquant

| Capacité demandée | État | Où (existant) | Écart |
|---|---|---|---|
| Chief Editor | ✅ | `editorial` : missions durables, 16 agents, approbations | — |
| Research Intelligence | ✅ | `lab` (théories, recherche), `knowledge` (recherche hybride) | — |
| Comic Intelligence | ✅ | `comic`, `vision` | — |
| Forensic Analysis | ✅ | `forensic` | — |
| Continuity & Fact Checking | ✅ | Continuity Editor, Fact Checker bloquant, veto des scripts | — |
| Audience Intelligence | ✅ | `audience` (phase 15) | lier les segments aux émissions (déjà possible via `series.segment_id`) |
| Market & Social Intelligence | ✅ | `market`, `social` | — |
| Content Opportunity | ✅ | `market.opportunity` | ajouter l'adéquation à une émission ou à un pilier |
| Storytelling & Narrative | ✅ | `storytelling` (13 étapes, niveaux, architectures) | lier chaque script à une émission, un format et une version de règles |
| Creative & Packaging | ✅ | `creative.packaging` | utiliser les profils visuels de l'émission |
| Brand Intelligence | 🟡 partiel | `brand_charter` (règles versionnées) | marque, piliers, profils de voix et visuels, règles par langue et plateforme, statut d'approbation |
| Franchise & Series | 🟡 partiel | `series`, `series_episode` | cycle de vie (test, suspension, retrait), formats, exigences de preuve, stratégie de langue, règles versionnées, historique de performance par émission |
| Distribution Intelligence | ❌ | — (déclinaisons sociales uniquement) | canaux, plan de diffusion, états proposé / approuvé / publié |
| Community Intelligence | ✅ | `audience.community` | rattacher la communauté au canal |
| Performance Intelligence | ✅ | `performance` (phases 11, 14, 19) | agréger par émission, format, langue et canal |
| Quality & Evaluation | ✅ | Fact Checker, notation des scripts, contrôles de niveau et de packaging | — |
| Rights & Source Intelligence | ❌ | références « à sourcer » (phase 10) | registre des sources et des droits : citations de cases, musique, voix, images |
| Editorial Memory | 🟡 partiel | missions, journaux par module, expériences | journal unique des décisions et leçons apprises **seulement depuis des résultats vérifiés** |
| Cost & Resource Intelligence | 🟡 partiel | `ai_gateway` (budget, zéro coût), `agent_run.cost_usd` | tableau des coûts et ressources par marque, émission et mission |

Voix institutionnelle : le module `voice` (phase 12) est un **assistant**. La narration des
productions exige des **profils de voix de marque** (voix de synthèse sous licence, ton,
langue). Aucun clonage de la voix du fondateur n'est requis ni proposé par défaut.

## 3. Réconciliation du modèle de données (aucune redondance)

| Entité demandée | Décision | Justification |
|---|---|---|
| `media_brands` | **NOUVELLE** | entité absente ; PRIMESTONE devient la première ligne, FR puis EN |
| `brand_guidelines` | **= `brand_charter` étendue** (+ `brand_id`, `language`, `status` DRAFT/APPROVED/RETIRED, `approved_by`, `approved_at`) | même rôle (règles versionnées) ; un renommage casserait l'existant sans bénéfice |
| `editorial_pillars` | **NOUVELLE** (marque, nom, description, règles, version, statut) | absente |
| `editorial_shows` | **= `series` étendue** (+ `brand_id`, cycle de vie DRAFT/TESTING/ACTIVE/SUSPENDED/RETIRED, `expertise_level`, `languages`, `evidence_requirements`, `pillar_id`) | `series` couvre déjà promesse, identité, segment, ton, structure, durée, direction artistique, distribution, évolution |
| versions des règles d'émission | **NOUVELLE `show_guideline_version`** | historique et approbation des changements d'une émission |
| `show_formats` | **NOUVELLE** (émission, nom, plateforme, langue, plage de durée, structure, règles, version) | absente |
| `show_episodes` | **= `series_episode` étendue** (+ `format_id`, `language`, `status` PROPOSED/IN_PRODUCTION/APPROVED/PUBLISHED, `content_id`, `guideline_version`) | même rôle |
| `brand_voice_profiles` | **NOUVELLE** (marque, langue, ton, type SYNTHETIC/HUMAN_LICENSED, fournisseur, voix, preuve de licence ou d'autorisation, statut) | absente ; le clonage du fondateur n'est jamais requis |
| `brand_visual_profiles` | **NOUVELLE** (marque, émission ou plateforme facultatives, règles, version) | variations de la charte par émission et par plateforme |
| `editorial_decisions` | **NOUVELLE** (objet, nature, proposition, statut PROPOSED/APPROVED/REJECTED/SUPERSEDED/REVERTED, politique, auteur, version, `supersedes`) | journal unique ; `approval_request` y sera relié, pas remplacé |
| `editorial_policies` | **NOUVELLE** (type d'action, approbation requise, approbateur, portée, version, actif) | les règles d'approbation sont aujourd'hui codées en dur |
| `content_portfolios` | **NOUVELLE** (marque, période, objectifs d'équilibre par pilier, niveau, langue et émission) + éléments reliés aux scripts et opportunités | absente |
| `distribution_channels` | **NOUVELLE** (marque, plateforme, langue, identifiant public, statut, état de l'autorisation des statistiques) | absente |
| `brand_experiments` | **= `experiment` étendue** (+ `brand_id`, `show_id`, `language`) | même rôle ; une nouvelle table dupliquerait le moteur statistique |
| registre droits et sources | **NOUVELLE `rights_record`** (objet, nature : case citée, musique, voix, image, licence, preuve, limites, échéance) | exigence « Rights & Source Intelligence » |

**Rattachements**, par colonnes facultatives avec remplissage par la marque par défaut :
- `script` : `brand_id`, `show_id`, `format_id`, `guideline_version` ;
- `content_item` : `brand_id`, `channel_id`, `show_id`, `language` (existe déjà) ;
- `mission` : `brand_id`, `show_id`.

Performance, audience et production suivent par ces liens, sans duplication.

## 4. Gouvernance

- **Réglages stratégiques du fondateur** : politiques (`editorial_policies`) modifiables
  uniquement par le fondateur ; chaque changement est une décision journalisée.
- **Trois états séparés partout** : PROPOSÉ (agents), APPROUVÉ (humain, selon la politique),
  PUBLIÉ. Les agents peuvent proposer, jamais approuver ce qui exige un humain, jamais publier.
- **Actions sensibles** : changement de charte ou de piliers, création, suspension ou retrait
  d'émission, validation finale d'un script, plan de diffusion, profil de voix, réglages de
  coût. Elles exigent toujours une approbation humaine.
- **Réversibilité** : décisions versionnées (`supersedes`, statut REVERTED) ; règles,
  émissions et formats versionnés ; rien n'est effacé.
- **Publication** : la plateforme ne publie **jamais** elle-même. « Publié » est un état
  déclaré par un humain, avec l'URL et le canal ; il relie le contenu à ses performances.

## 5. International (FR puis EN)

Les briques existent déjà : adaptation de script reliée (phase 10), variantes de niveau
(phase 17), packaging par script (phase 18). À ajouter :
- règles, piliers et profils **par langue** ;
- formats et canaux par langue ;
- émissions déclarant leur stratégie de langue ;
- recherche factuelle partagée (même corpus, mêmes preuves), décisions éditoriales distinctes
  par langue.

La traduction littérale reste exclue : une version EN est une réécriture reliée, soumise au
même Fact Checker.

## 6. Phases proposées

| Phase | Contenu | Dépend de | Coût |
|---|---|---|---|
| 20 | **Marque et gouvernance** : `media_brands`, règles étendues (statut, langue, approbation), piliers, politiques, journal des décisions, réglages du fondateur, rattachement `brand_id` | 18 | 0 € |
| 21 | **Moteur d'émissions** : cycle de vie complet, `show_formats`, versions des règles, épisodes étendus, exigences de preuve, historique de performance par émission, adéquation des opportunités aux émissions et aux piliers | 20 | 0 € |
| 22 | **Identité indépendante** : profils de voix (synthétiques sous licence, locaux et gratuits), profils visuels, règles par langue, mission « narration » utilisant la voix de marque | 20, 21 | 0 € (Piper local) |
| 23 | **Distribution et portefeuille** : canaux, plan de diffusion (proposé, approuvé, publié déclaré), portefeuille de contenus équilibré (piliers, niveaux, langues), performance par canal | 21 | 0 € |
| 24 | **Droits, mémoire, coûts** : registre des droits et sources, mémoire éditoriale (leçons depuis résultats OBSERVED ou DEMONSTRATED uniquement), tableau des coûts et ressources | 20 à 23 | 0 € |

## 7. Critères d'acceptation

- **20** : une seule marque par défaut créée par migration ; toute donnée existante y est
  rattachée ; changer la charte crée une proposition qui reste sans effet tant que le
  fondateur ne l'a pas approuvée ; toute décision est journalisée et réversible.
- **21** : créer, tester, activer, suspendre et retirer une émission, chaque transition
  étant une décision ; une émission suspendue n'accepte plus de nouvel épisode ; un épisode
  respecte un format, et un écart est signalé ; la performance est agrégée par émission.
- **22** : produire un épisode sans voix ni visage du fondateur ; un profil de voix sans
  licence enregistrée est refusé ; une règle FR ne s'applique pas à un contenu EN.
- **23** : aucun contenu ne passe à PUBLIÉ sans déclaration humaine ; le portefeuille signale
  ses déséquilibres ; aucune publication automatique.
- **24** : une leçon n'est enregistrée que depuis une preuve OBSERVED ou DEMONSTRATED ; toute
  citation de case utilisée en production a un enregistrement de droits ; coûts visibles par
  émission et par mission.
- **Partout** : tests verts, migrations additives et réversibles, aucun appel payant, aucune
  fonctionnalité existante cassée (suite complète).

## 8. Implications de sécurité et d'exploitation, risques

- **Migrations sur tables existantes** : colonnes facultatives uniquement, plus un
  remplissage vers la marque par défaut ; aller-retour testé ; aucune perte possible.
- **Gouvernance appliquée côté serveur** : une politique se contrôle dans le service, pas
  dans l'interface ; les tests doivent prouver qu'un agent ne peut pas approuver.
- **Identité** : le fondateur est authentifié par IAP (phase 13). Pas de comptes
  multi-utilisateurs pour l'instant (usage personnel), mais les décisions portent leur auteur.
- **Voix de synthèse** : les voix ont des licences variables. Chaque profil enregistre la
  licence et l'usage autorisé ; aucun clonage sans autorisation écrite de la personne.
- **Droits** : en France, le droit de courte citation est limité. Le registre ne juge pas la
  légalité : il trace la source, l'usage et les limites, pour décision humaine.
- **Complexité** : 8 tables nouvelles et 6 enrichies, réparties sur 5 phases, aucun
  microservice. Les « 18 capacités » restent des responsabilités logiques dans le monolithe
  modulaire (ADR-0001).
- **Dépendance aux agents** : une émission stocke ses exigences (format, preuves, ton), pas
  un agent ; tout agent capable peut produire pour elle.

## 9. Décisions à valider par le fondateur

1. Étendre `brand_charter`, `series`, `series_episode` et `experiment` plutôt que créer des
   tables homonymes (ou préférer un renommage, plus coûteux).
2. Les cinq phases 20 à 24 et leur ordre.
3. La liste des actions qui exigent ton approbation (section 4), modifiable ensuite.
4. Les émissions initiales à créer comme brouillons : PRIMESTONE COSMOS, THE COMIC FILES,
   BEYOND THE PANEL, THE VERDICT (concepts, non définitifs).
5. Une voix de synthèse locale et gratuite (Piper) comme voix institutionnelle par défaut,
   à choisir et faire valider par toi.
