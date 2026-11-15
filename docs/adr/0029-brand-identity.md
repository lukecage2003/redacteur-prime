# ADR-0029 — Identité indépendante : voix, visuels et règles par langue

- Statut : Accepté
- Date : 2026-11-15
- Contexte : [audit « média autonome »](../audit/autonomous-media-brand.md), phase 22 ; ADR-0027.

## Décision

1. **Voix de marque** (`brand_voice_profile`) : langue, ton, nature (SYNTHETIC ou
   HUMAN_LICENSED), fournisseur, voix, **licence et usage autorisé obligatoires**
   (contraintes en base et contrôles du service). Une voix humaine exige une référence
   d'autorisation écrite. Le clonage de la voix du fondateur n'est jamais requis ni proposé.
2. **Approbation** : un profil naît PROPOSED et passe par une décision `VOICE_PROFILE`
   (approuvé, rejeté → RETIRED, annulé → RETIRED). Seule une voix APPROUVÉE est utilisable.
3. **Règles par langue** : charte et profils visuels portent une langue facultative. Une
   règle de langue s'applique uniquement à cette langue ; une règle sans langue vaut pour
   toutes. Résolution des profils visuels du plus général au plus précis (marque → plateforme
   → langue → émission). Le packaging utilise la charte de la langue du script.
4. **Profils visuels** (`brand_visual_profile`) : nouvelle version par portée (émission,
   plateforme, langue), l'ancienne est retirée et conservée.
5. **Narration** (`narration@1`) : plan par sections du script (références de pages
   retirées, durée estimée), voix approuvée de la langue du script ; synthèse facultative par
   un modèle local gratuit (Piper) vers le stockage d'objets. Aucune voix, aucun visage du
   fondateur ; aucune publication.

## Conséquences

- Les gestionnaires de gouvernance acceptent un crochet de rejet (`register_reject_hook`).
- Le choix du modèle Piper et de sa licence revient au fondateur : aucune voix n'est créée
  par défaut, aucune licence n'est présumée.
- Pas de mission éditoriale NARRATION à ce stade : le service, l'API et la CLI suffisent.
