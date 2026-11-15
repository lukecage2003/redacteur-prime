# ADR-0027 — Marque média et gouvernance éditoriale

- Statut : Accepté
- Date : 2026-11-15
- Contexte : [audit « média autonome »](../audit/autonomous-media-brand.md), phase 20.

## Décision

1. **La marque est l'entité centrale** : `media_brand` (PRIMESTONE créée par défaut, FR
   principal, EN de premier rang). Séries, scripts, contenus, missions, expériences et chartes
   portent un `brand_id` ; l'existant est rattaché à PRIMESTONE par la migration 0015.
2. **Gouvernance proposé → approuvé → appliqué** : toute action sensible crée une ligne
   `editorial_decision` (action, sujet, proposition, auteur, version de politique).
   - Seul le rôle **FOUNDER** approuve, rejette ou annule ; un agent ne peut que proposer.
     La règle est imposée dans `GovernanceService`, pas dans l'interface.
   - Une action sans politique connue exige l'approbation (défaut prudent).
   - `editorial_policy` dit, par action, si l'approbation est exigée ; les actions non
     sensibles (ex. `PACKAGING_PROPOSAL`) s'appliquent d'office **mais restent journalisées**
     (`decided_by = POLICY`).
   - `POLICY_CHANGE` exige toujours l'approbation et ne peut jamais devenir automatique.
3. **Réversibilité exacte** : l'application mémorise l'état antérieur dans la décision
   (`proposal.previous`) ; l'annulation (`REVERTED`, motif obligatoire) le restaure. Rien
   n'est supprimé.
4. **Charte = règles de marque approuvées** : `publish_charter` crée un **brouillon** soumis
   (`CHARTER_CHANGE`) ; seule la dernière version APPROUVÉE s'applique au packaging.
   Approuver une version retire la précédente (même marque, même langue) ; l'annuler la
   rétablit.
5. **Extensible** : les phases 21 à 24 enregistrent leurs gestionnaires
   (`register_handler`) pour `SHOW_LIFECYCLE`, `DISTRIBUTION_PLAN`, `VOICE_PROFILE`,
   `COST_SETTINGS`, `SCRIPT_FINAL_VALIDATION`. Sans gestionnaire, la décision est journalisée
   sans effet de bord.

## Conséquences

- Aucune publication ni changement de marque sans le fondateur ; journal complet et auditable.
- L'API (protégée par IAP, réservée au propriétaire) et la CLI décident avec le rôle FOUNDER ;
  les agents n'ont accès qu'au service, avec un autre rôle.
- Pas de nouveau service déployé : un sous-paquet `primestone.governance` du monolithe.
