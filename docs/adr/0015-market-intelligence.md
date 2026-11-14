# ADR-0015 — Market Intelligence : données publiques gratuites, fiche validée, score explicite

- Statut : Accepté
- Date : 2026-11-14

## Contexte

L'objectif : repérer les sujets de comics très demandés en anglais et encore peu traités en
français. Le propriétaire impose un coût nul et le projet interdit d'inventer des métriques
privées de concurrents (CTR, rétention, impressions).

## Décision

1. **Sources avec fiche** (`market_source`) : accès, quota, URL des conditions, classe de
   données, langue. **Aucune collecte** tant qu'un humain n'a pas validé la fiche
   (`verified_at`, `verified_by`).
2. **Connecteurs gratuits** :
   - YouTube Data API v3 : gratuite dans la limite d'un quota de 10 000 unités par jour. La
     recherche coûte 100 unités, les statistiques 1 unité pour 50 vidéos. Le quota du jour est
     calculé depuis les collectes tracées et une collecte qui le dépasserait est refusée avant
     tout appel. La clé passe par une variable d'environnement en local et par Secret Manager
     dans le cloud ; elle n'apparaît jamais dans les erreurs.
   - Flux RSS et Atom en HTTPS : bibliothèque standard, DOCTYPE et ENTITY refusés, 5 Mo maximum.
   - Import manuel (CSV, JSON ou API) de relevés publics.
   - Reddit n'est pas implémenté : son API exige désormais une application OAuth approuvée.
3. **Métriques publiques uniquement** : contraintes en base `metric IN (views, likes, comments)`
   et `data_class = 'PUBLIC'`. L'import refuse ctr, retention, impressions et watch_time. Un
   compteur masqué par la plateforme est absent, jamais mis à 0.
4. **Instantanés horodatés** : append-only, idempotents par (contenu, métrique, instant).
   `snapshot` collecte toutes les sources validées et se lance une fois par jour (cron local
   ou, plus tard, Cloud Scheduler).
5. **Analyse `market-gap@1`** : pure, testée, chaque chiffre expliqué. Sur la fenêtre choisie,
   et pour chaque sujet (mots-clés FR/EN) :
   - offre = nombre de contenus ;
   - demande = médiane des vues, exigée sur au moins `min_items` contenus, sinon
     INSUFFICIENT_DATA ;
   - demande EN normalisée : échelle logarithmique ;
   - saturation FR = min(1, n_FR / n_EN) ;
   - écart = demande EN × (1 − saturation FR) ;
   - différence culturelle = log du rapport des médianes FR/EN.

   Tout résultat est ESTIMATE et renvoie à ses contenus sources (classe PUBLIC).
6. **Market Analyst** (agent du Chief Editor) et mission `MARKET_BRIEF` : la note de marché est
   toujours « VALIDER AVEC RÉSERVES », ou « NE PAS VALIDER » sans données. Elle ne cite aucune
   page de comic, donc le Fact Checker ne s'applique pas ; c'est affiché.

## Conséquences

- Le score reflète l'échantillon collecté (requêtes et flux choisis), pas toute la plateforme.
  C'est écrit dans chaque résultat.
- Une recherche YouTube renvoie au plus 50 résultats : sur les sujets très traités, les
  comptages saturent. La saturation est donc relative, entre langues, à requête égale.
- Sans clé YouTube ni accès réseau aux hôtes des sources, seuls l'import manuel et l'analyse
  fonctionnent.
