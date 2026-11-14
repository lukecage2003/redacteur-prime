# ADR-0009 — Stockage adressé par contenu et profils de rendu versionnés

- Statut : Accepté
- Date : 2026-11-14

## Contexte

La bibliothèque doit absorber des lots de 50 comics ou plus, être reprenable après panne,
éviter de stocker ou de traiter deux fois le même fichier, et permettre de changer la qualité
de rendu sans écraser l'existant.

## Décision

- Un document est identifié par le SHA-256 de son contenu (`document.sha256` unique).
  Clés : `originals/<sha[:2]>/<sha>.<format>`.
- Les rendus sont rangés par profil : `renders/<sha[:2]>/<sha>/<profil>/<page>.webp`, avec un profil
  nommé d'après ses paramètres (ex. `webp-d2400-q85`). Changer de profil produit de nouvelles
  clés et de nouvelles étapes (clé d'idempotence incluant le profil) sans toucher aux anciens rendus.
- Écritures atomiques (fichier temporaire puis renommage) ; en GCS, les objets sont atomiques
  par nature.
- WebP qualité 85, plus grand côté 2 400 px : lisible en plein écran, adapté à l'OCR et à
  l'analyse visuelle (phase 3), environ 3 à 6 fois plus léger qu'un PNG.
- Le format est détecté par signature, jamais par l'extension ; les archives ne sont jamais
  extraites sur disque.

## Conséquences

Ré-import instantané (0,25 s pour 60 doublons mesurés). Le cache des analyses IA (phase 3+)
pourra utiliser la même clé `(sha256, page, profil, version de prompt)`. Le nettoyage d'anciens
profils devra être explicite (jamais automatique).
