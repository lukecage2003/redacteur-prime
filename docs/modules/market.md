# Market Intelligence (phases 2b et 8)

Code : `packages/primestone/src/primestone/market/` · ADR-0015 · coût : **nul**.

## Rôle

Trouver les sujets de comics très regardés en anglais et peu traités en français (écart EN→FR),
les niches, les sujets déjà saturés en français et les différences culturelles. Le module ne
travaille que sur des **données publiques**, et chaque chiffre est expliqué.

## Mise en route (gratuite)

1. **Déclarer une source avec sa fiche**, puis la **valider** après avoir relu les conditions :

   ```bash
   uv run primestone-market add-source youtube --name "YouTube Data API v3" --kind YOUTUBE_API \
     --access "clé d'API, données publiques" --quota "10 000 unités/jour, gratuit" \
     --terms-url https://developers.google.com/youtube/terms/api-services-terms-of-service
   uv run primestone-market verify youtube
   ```

2. **Clé YouTube** (facultative, gratuite) : dans un projet Google Cloud, activer
   « YouTube Data API v3 » et créer une clé d'API (aucune facturation requise). La mettre dans
   `.env` en local (`PRIMESTONE_YOUTUBE_API_KEY=…`) et dans Secret Manager dans le cloud.
   L'environnement doit autoriser l'hôte `www.googleapis.com`.

3. **Définir des sujets** :

   ```bash
   uv run primestone-market topic Sandman --fr sandman --en sandman
   ```

4. **Collecter** :
   - une source : `collect youtube --query sandman --language en` ;
   - toutes les sources validées : `snapshot`, à lancer une fois par jour par cron (par exemple
     `0 6 * * * uv run primestone-market snapshot`).

   Sans réseau : `import` d'un CSV de relevés publics faits à la main.

5. **Analyser** : `analysis`, la page web `/market`, ou la note du Chief Editor
   (`brief --process`).

## Entrées / sorties

| Action | API | CLI |
|---|---|---|
| Sources | `GET/POST /market/sources`, `POST /market/sources/verifications` | `sources`, `add-source`, `verify` |
| Import manuel | `POST /market/imports` (champs inconnus refusés) | `import KEY fichier.csv` |
| Collecte | `POST /market/collections`, `GET /market/collections` | `collect`, `snapshot`, `collections` |
| Sujets | `GET/POST /market/topics` | `topic`, `topics` |
| Analyse | `GET /market/analysis?window_days=&min_items=` | `analysis` |
| Note de marché | `POST /editorial/missions {"type": "MARKET_BRIEF"}` | `brief [--process]` |

## Règles

- Aucune collecte avant la validation humaine de la fiche.
- Les seules métriques stockables sont views, likes et comments (classe PUBLIC). Une contrainte
  en base refuse toute autre métrique, et l'import refuse ctr, retention, impressions et
  watch_time.
- Le quota gratuit YouTube n'est jamais dépassé : l'appel est refusé avant, et le quota repart
  à minuit, heure du Pacifique.
- En dessous de `min_items` contenus avec des vues, aucun score n'est calculé
  (INSUFFICIENT_DATA) : rien n'est extrapolé.
- Tous les résultats ont la classe ESTIMATE ; les contenus sources ont la classe PUBLIC.

## Méthode `market-gap@1`

- demande EN = log10(1 + médiane EN) / log10(1 + plus forte médiane EN) ;
- saturation FR = min(1, n_FR / n_EN) ;
- écart = demande EN × (1 − saturation FR) ;
- différence culturelle = log10((1 + médiane FR) / (1 + médiane EN)) ; une valeur positive veut
  dire que le sujet marche relativement mieux en français ;
- niche : au moins 3 sujets chiffrés, offre EN sous la médiane des sujets et demande ≥ 0,5.

## Limites

- Le score porte sur l'échantillon collecté (requêtes et flux choisis), pas sur toute la
  plateforme. Une recherche YouTube renvoie au plus 50 résultats.
- La langue d'une vidéo vient de la langue audio déclarée, à défaut de la langue demandée.
- Reddit n'est pas implémenté (application OAuth approuvée exigée). TikTok et Instagram n'ont
  pas d'API publique gratuite pour ces données.
- Pas encore validé sur des données réelles : ce conteneur n'a pas accès au réseau des
  plateformes.

## Tests

- `packages/primestone/tests/test_market_connectors.py` : RSS/Atom, YouTube simulé, quota, clé
  jamais divulguée, analyse.
- `packages/primestone/tests/test_market_service.py` : fiches, import, contraintes, quota,
  traces d'échec, mission.
- `apps/api/tests/test_market_api.py`.
- `apps/web/lib/market.test.ts`.

## Phase 16 — Opportunités éditoriales (ADR-0023)

`uv run primestone-market opportunities`, la section « Opportunités » de `/market`, ou la
mission `primestone-market opportunity-brief --process`.

Pour chaque sujet suivi, la fiche donne :
- le public potentiel, le besoin identifié, l'angle différenciant ;
- les preuves disponibles (pages transcrites) et la concurrence francophone ;
- les risques, les formats possibles, une recommandation ;
- un score expliqué et un niveau de confiance.

Sans demande francophone **observée**, le sujet reste une hypothèse, quelle que soit sa
popularité en anglais.
