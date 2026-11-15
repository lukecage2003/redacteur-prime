# ADR-0021 — Mesure par objectif, expériences rigoureuses, OAuth de la chaîne

- Statut : Accepté
- Date : 2026-11-15

## Décision

1. **Objectif par contenu** : DISCOVERY, EXPLORATION, EXPERTISE ou COMMUNITY ; format
   (LONG, SHORT, REEL…). Chaque contenu est jugé sur les indicateurs de **son** objectif et
   comparé à la médiane des contenus de même objectif et de même format (`objective-kpi@1`),
   à partir de 3 pairs. Jamais sur les seules vues. Un contenu sans objectif n'est pas évalué.
2. **Mesure élargie** : partages, abonnés perdus, spectateurs connus, nouveaux et uniques,
   enregistrements, vues engagées ; segments **agrégés** (source de trafic, pays, tranche
   d'âge, appareil). Une métrique non fournie n'est jamais estimée.
3. **Courbes de rétention** (`retention_point`) depuis YouTube Analytics (rapport
   `elapsedVideoTimeRatio`), conservées par instantané.
4. **Expériences** (`ab-proportion@1`) : hypothèse, variable, audience, format, période,
   métrique, variantes.
   - Gagnant seulement avec des comptes : au moins 1 000 expositions et 30 succès par
     variante, et p < 0,05 (test bilatéral de deux proportions, intervalles de Wilson).
     Sinon INCONCLUSIVE, avec la raison.
   - Les parts rapportées par « Tester et comparer » de YouTube sont enregistrées comme verdict
     de la plateforme, jamais comme démonstration.
   - Une expérience close n'est plus modifiable.
5. **Niveaux de preuve** : OBSERVED (mesures), HYPOTHESIS (corrélations `perf-learn@1`),
   DEMONSTRATED (expérience concluante, dans son contexte uniquement).
6. **OAuth « application installée »** (redirection locale 127.0.0.1, lecture seule,
   gratuit) : seul le jeton de rafraîchissement est conservé, dans `.env` ou Secret Manager,
   jamais journalisé.

## Conséquences

- La boucle d'apprentissage repose sur des bases honnêtes : un résultat se mérite.
- Avec peu de vidéos, la plupart des verdicts seront « repère insuffisant » ou
  « non concluant ». C'est voulu.
