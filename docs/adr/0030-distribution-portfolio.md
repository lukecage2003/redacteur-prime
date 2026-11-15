# ADR-0030 — Distribution et portefeuille

- Statut : Accepté
- Date : 2026-11-15
- Contexte : [audit « média autonome »](../audit/autonomous-media-brand.md), phase 23 ; ADR-0027.

## Décision

1. **Canaux** (`distribution_channel`) : plateforme, langue, identifiant public, statut
   (ACTIVE/PAUSED/RETIRED), état de l'autorisation des statistiques (NONE, CSV_EXPORT,
   OAUTH_READONLY). Les contenus portent leur canal (`content_item.channel_id`).
2. **Plan de diffusion** (`distribution_item`) : PROPOSED → APPROVED (décision
   `DISTRIBUTION_PLAN`, refusée si le script lié n'est pas VALIDÉ) → PUBLISHED, ou CANCELLED
   (rejet, annulation). Un script ne part que sur un canal de sa langue (adapter, pas
   traduire) ; un canal en pause ou une émission fermée n'accepte rien.
3. **Publication seulement déclarée** : la plateforme ne publie jamais. Le propriétaire publie
   lui-même, puis déclare l'URL https et l'identifiant public ; la contrainte en base exige
   contenu et déclarant pour PUBLISHED. La déclaration crée ou relie le `content_item` (donc
   ses statistiques) et marque l'épisode approuvé comme publié. Une publication ne peut pas
   être « annulée » par décision.
4. **Portefeuille** (`content_portfolio`, `portfolio@1`) : période et parts visées par
   pilier, niveau, langue et émission ; comparaison au plan (hors éléments annulés), écarts
   au-delà de 15 points signalés. Aucune table d'éléments : le portefeuille se calcule à partir
   du plan, sans duplication.
5. **Performance par canal** : agrégats des dernières mesures autorisées ; « NON FOURNI »
   sans données.

## Conséquences

- Aucune intégration de publication (API de mise en ligne) n'est ajoutée, volontairement.
- Le gestionnaire d'agrégats est partagé avec le moteur d'émissions (`shows.aggregate`).
