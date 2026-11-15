# Extension « Audience, Growth & Creative Intelligence » : analyse des dépendances

- Date : 2026-11-15
- Statut : **PROPOSITION, en attente de validation humaine.** Aucun code n'est écrit avant
  validation.

## 1. Principe directeur : regrouper, ne pas empiler

Les 15 exigences recoupent largement ce qui existe déjà : marché (8), social (9), scripts (10),
performance (11), graphe (5), laboratoire (7). Plutôt que 11 nouveaux modules, la proposition
compte :

- **2 nouveaux paquets** :
  - `audience` : audiences, segments, communauté ;
  - `creative` : packaging, marque, séries, bibliothèque de techniques.
- **4 paquets étendus** :
  - `market` : opportunités ;
  - `storytelling` : niveaux, architectures, rétention côté script ;
  - `social` : formats supplémentaires ;
  - `performance` : laboratoire, expériences, mesure par objectif.
- **Aucun nouveau graphe** : l'*Audience Knowledge Graph* réutilise le graphe prouvé existant
  (ADR-0012), avec de nouveaux types d'entités et de relations, chaque lien portant sa preuve.

## 2. Correspondance exigences → architecture

| # | Exigence | Où | Existant réutilisé | Nouveau |
|---|---|---|---|---|
| 1 | Audience Intelligence | `audience` (nouveau) | graphe de connaissances, performance, marché | segments HYPOTHESIS / CONFIRMED (avec preuves), motivations, formats, plateformes ; entités AUDIENCE_SEGMENT, FORMAT, MOTIVATION dans le graphe |
| 2 | Audience Bridge (Discovery / Exploration / Expertise) | `storytelling` | scripts, adaptations reliées, Fact Checker, laboratoire | niveau de script, variantes reliées par niveau, contrôles propres à chaque niveau (jargon, contexte minimal ; preuves et contre-preuves en Expertise) ; **même Fact Checker pour les trois** |
| 3 | Content Opportunity | `market` | écart EN→FR, laboratoire, complétude documentaire, graphe | score d'opportunité multicritère expliqué ; « popularité EN » séparée de la « demande FR observée » |
| 4 | Packaging Intelligence | `creative` (nouveau) | faits vérifiés, Fact Checker, ai_gateway (local) | 10 titres, 5 concepts de miniature, 3 promesses, 3 accroches ; contrôle d'honnêteté (promesse ↔ script), lisibilité, adéquation au segment ; **aucune prédiction de CTR** |
| 5 | Retention Intelligence | `storytelling` + `performance` | pré-notation des scripts, import Studio | analyse du script (longueurs, répétitions, transitions, révélations) ; courbes de rétention réelles ; contrat Motion Studio 1.1 (intentions narratives, moments visuels) |
| 6 | Community Intelligence | `audience` | recherche hybride, plongements locaux | commentaires publics de **sa propre chaîne** (API YouTube gratuite), regroupement de questions, propositions (sondages, vidéos réponses) ; **aucune interaction automatisée** |
| 7 | Franchise & Series | `creative` | scripts, social | série : promesse, identité, segment, ton, structure, durée, direction artistique, distribution, évolution |
| 8 | Cross-Platform | `social` | déclinaisons de la phase 9, adaptation FR/EN | Shorts, posts communautaires, podcast, dossier écrit ; versions FR/EN adaptées (pas traduites) |
| 9 | Creative Intelligence | `creative` + `storytelling` | gabarits de structure | bibliothèque de **principes** narratifs (jamais de textes ou séquences d'autres créateurs) ; plusieurs architectures pour un même sujet |
| 10 | Brand Intelligence | `creative` | — | charte (couleurs, typographies, ton, règles de miniature, habillage) ; contrôles de cohérence sur packaging et séries |
| 11 | Content Performance Lab | `performance` | boucle `perf-learn@1` | autopsie de vidéo, laboratoire d'accroches, décrochages, spectateurs récurrents ; observé / hypothèse / causalité démontrée séparés |
| 12 | Méthode de mesure | `performance` | 9 métriques actuelles | objectif par contenu (DISCOVERY, INVESTIGATION, COMMUNITY…) et indicateurs adaptés ; partages, abonnés, spectateurs récurrents, par segment et par format |
| 13 | Expérimentation | `performance` | — | registre d'expériences (hypothèse, variable, audience, format, période, métrique) ; tests statistiques ; **pas de gagnant sur échantillon insuffisant** ; import des résultats « Tester et comparer » de YouTube |
| 14 | Éthique | transverse | Fact Checker, DataClass, contraintes en base | détecteur de titres trompeurs, interdiction d'engagement artificiel, garde-fous « public mineur » (aucune donnée personnelle, agrégats seulement) |
| 15 | Validation | tests + ROADMAP | statuts existants | un critère d'acceptation par point, démontré sur données réelles |

## 3. Graphe de dépendances

```
11 Performance ──► 14 Mesure & expérimentation ──► 15 Audience & communauté ──► 16 Opportunités
                                                          │                          │
10 Storytelling ─────────────────────────────────► 17 Bridge, architectures, ◄──────┘
 9 Social ──────────────────────────────────────►    rétention script, multi-plateforme
                                                          │
                                       18 Packaging, marque, séries (creative)
                                                          │
                                       19 Performance Lab & validation finale
```

Pourquoi cet ordre :

1. **La mesure d'abord (14).** Sans objectifs par contenu ni expériences rigoureuses, aucun
   moteur ne peut « apprendre ». C'est le socle de 4, 11 et 13.
2. **L'audience ensuite (15).** Opportunités, packaging et niveaux de script ont besoin de
   segments, d'abord hypothétiques, puis confirmés par les données.
3. **Les opportunités (16)** croisent marché, audience, documentation disponible et identité.
4. **La création (17, 18)** s'appuie sur les segments et les opportunités.
5. **Le laboratoire complet (19)** boucle sur des vidéos réellement publiées.

## 4. Phases proposées

| Phase | Contenu | Exigences | Dépend de | Coût |
|---|---|---|---|---|
| 14 | Mesure par objectif & expérimentation scientifique | 12, 13, 14 (partie mesure) | 11 | 0 € |
| 15 | Audience Intelligence & communauté | 1, 6, 15.1–15.2 | 5, 8, 11, 14 | 0 € (clé YouTube gratuite) |
| 16 | Content Opportunity Engine | 3, 15.3 | 7, 8, 15 | 0 € |
| 17 | Audience Bridge, architectures narratives, rétention script, multi-plateforme FR/EN | 2, 5 (script), 8, 9, 15.4, 15.10, 15.11 | 9, 10, 15 | 0 € |
| 18 | Packaging, marque, séries & franchises | 4, 7, 10, 14 (titres), 15.5, 15.9, 15.12 | 14, 15, 17 | 0 € (modèle local facultatif) |
| 19 | Content Performance Lab & validation finale | 5 (vidéo), 11, 15.6–15.8, 15.13 | 14, 18 | 0 € (OAuth gratuit) |

## 5. Ce que les données permettent réellement (gratuit, autorisé)

| Donnée | Source | Accès | Statut |
|---|---|---|---|
| Vues, CTR, rétention moyenne, abonnés | export CSV YouTube Studio | aucun | disponible (phase 11) |
| Courbes de rétention, spectateurs récurrents, sources de trafic, âge et pays **agrégés** | YouTube Analytics API (OAuth de ta chaîne) | gratuit | **à autoriser** : principal levier |
| Résultats « Tester et comparer » (miniatures, titres) | YouTube Studio | saisie ou export | disponible manuellement |
| Commentaires publics de **ta** chaîne | YouTube Data API v3 | clé gratuite | **à créer** |
| Tendances publiques EN/FR | YouTube Data API, RSS | clé gratuite | phase 8 prête |
| Reddit, forums | API officielles | application OAuth approuvée | BLOCKED |
| Statistiques TikTok / Instagram | comptes professionnels + revue d'application | — | export manuel uniquement |
| Satisfaction (enquêtes YouTube) | non exposée par l'API | — | non disponible : ne sera jamais inventée |

## 6. Limites assumées

- **Génération créative** (titres, accroches, concepts de miniatures) : sans modèle, on ne
  peut produire que des gabarits à partir des faits vérifiés. Un modèle **local** gratuit
  (Ollama) améliore nettement le résultat, toujours sous contrôle d'honnêteté et du Fact
  Checker.
- **Miniatures** : des concepts décrits (composition, texte, émotion, cohérence de marque),
  pas des images générées. L'analyse visuelle de miniatures réelles exige un modèle de vision
  local (facultatif).
- **Causalité** : le système distingue observé, hypothèse et causalité ; seule une expérience
  contrôlée avec un échantillon suffisant peut conclure.
- **Mineurs** : segmentation par motivations et par niveau de connaissance, jamais par âge ;
  les tranches d'âge agrégées de YouTube servent seulement à adapter le contenu (pas de
  données personnelles).

## 7. Décisions à valider par le propriétaire

1. Le regroupement en 2 nouveaux paquets et 4 extensions, et l'ordre des phases 14 à 19.
2. L'autorisation OAuth YouTube Analytics de ta chaîne (gratuite, lecture seule) : elle
   débloque rétention, décrochages, spectateurs récurrents et segments confirmés.
3. Le recours à un modèle local Ollama pour la génération créative (gratuit, sur ta machine).
4. La charte de marque initiale (couleurs, typographies, ton), que tu fournis.
5. Un périmètre communauté limité au départ aux commentaires publics de ta propre chaîne.
