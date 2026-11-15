# ADR-0028 — Moteur d'émissions gouverné

- Statut : Accepté
- Date : 2026-11-15
- Contexte : [audit « média autonome »](../audit/autonomous-media-brand.md), phase 21 ; ADR-0027.

## Décision

1. **Une émission est une `series` étendue**, pas une nouvelle table : cycle de vie
   DRAFT → TESTING → ACTIVE ⇄ SUSPENDED → RETIRED (retrait possible depuis tout état non
   retiré), niveau d'expertise, langues, exigences de preuve, pilier, version des règles.
   L'existant est conservé (PAUSED → SUSPENDED, ENDED → RETIRED).
2. **Chaque transition est une décision `SHOW_LIFECYCLE`** du fondateur ; la création propose
   automatiquement DRAFT → TESTING. Une seule transition en attente à la fois ; le
   gestionnaire vérifie l'état attendu avant d'appliquer ou d'annuler.
3. **Règles versionnées** : `show_guideline_version` conserve chaque proposition (décision
   `SHOW_GUIDELINES`, nouvelle politique sensible). L'application mémorise les valeurs
   antérieures ; l'annulation les restaure, version comprise. Champs modifiables : liste
   fermée (promesse, identité, ton, structure, durée, direction artistique, évolution,
   niveau, pilier, distribution, langues, exigences de preuve).
4. **Formats** (`show_format`) : plateforme, langue (parmi celles de l'émission), plage de
   durée, structure, règles ; retirés, jamais supprimés.
5. **Épisodes** : seule une émission TESTING ou ACTIVE en accepte ; format et langue
   cohérents ; version des règles figée à l'ajout ; conformité au format (durée estimée,
   étapes absentes) signalée, jamais masquée. Statuts PROPOSED → IN_PRODUCTION → APPROVED
   (décision `SCRIPT_FINAL_VALIDATION`, refusée si le script n'est pas VALIDÉ par la
   vérification factuelle) → PUBLISHED (déclaration du propriétaire, liée à un contenu
   importé ; aucune publication automatique).
6. **Performance par émission** : agrégats des dernières mesures AUTORISÉES de ses contenus,
   par langue et par format ; « NON FOURNI » sans données ; aucune causalité.
7. **Adéquation sujet → émissions et piliers** (`show-fit@1`) : recouvrement lexical
   indicatif ; le choix revient au fondateur.

## Conséquences

- `script`, `content_item`, `mission`, `experiment` portent `show_id` ; `script` porte
  `format_id` ; `experiment` porte `language` (migration 0016, additive et réversible).
- Les gestionnaires de gouvernance sont chargés à la demande (pas de cycle d'import).
