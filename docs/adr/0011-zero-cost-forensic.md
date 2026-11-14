# ADR-0011 — Mode zéro coût et forensique par règles déterministes

- Statut : Accepté
- Date : 2026-11-14

## Contexte

Le propriétaire exige que la plateforme ne lui coûte rien. La phase 4 doit pourtant produire
des observations forensiques prouvées, distinguer CANON / INTERPRÉTATION, et repérer
contradictions et indices.

## Décision

1. **Mode zéro coût, activé par défaut** (`PRIMESTONE_ZERO_COST=true`) : un fournisseur payant
   est refusé dès sa création ; toute estimation non nulle est refusée au lancement ; tout appel
   dont le coût prévu est non nul est refusé avant exécution. Le désactiver exige un geste
   explicite.
2. **Sources de texte gratuites** :
   - transcription **humaine** (interface web ou API) : source la plus fiable, toujours CANON ;
   - **modèle local** via Ollama (open source, exécuté sur la machine de l'utilisateur), même
     interface et même schéma de sortie que l'adaptateur Claude ;
   - le fournisseur Claude reste disponible mais désactivé.
3. **Forensique sans modèle** : extracteurs à règles (`forensic-rules@1.0.0`) sur les
   transcriptions servies : textes lettrés, répliques attribuées, mentions de personnages,
   premières attestations, affirmations (âge, identité), contradictions candidates, variantes
   de noms. Chaque observation porte au moins une référence exacte (document, page, case,
   zone, extrait).
4. **Discipline de preuve** :
   - texte CANON seulement si humain ou confiance ≥ 0,9 ;
   - attribution d'une réplique CANON seulement si validée par un humain ;
   - une affirmation de personnage est rapportée comme affirmation, jamais comme fait ;
   - contradictions et variantes sont des candidats (INTERPRETATION), avec explications
     alternatives ;
   - « première attestation » rétrogradée en INTERPRETATION si le document est incomplet ;
   - rapport INCOMPLETE tant qu'une page n'est pas transcrite.
5. **Ajout seul** : une correction humaine crée une nouvelle version ; les observations qui
   s'appuient sur une version remplacée restent en base mais ne sont plus servies.

## Conséquences

Coût d'exploitation nul en local. Le rappel dépend de la quantité de texte transcrit ; la
précision du texte est maximale quand il est saisi par un humain. Les règles d'affirmation
(âge, identité FR/EN) sont volontairement étroites : peu de faux positifs, à élargir par
mesure. Les théories (preuves, contre-preuves, alternatives) relèvent de la phase 7.
