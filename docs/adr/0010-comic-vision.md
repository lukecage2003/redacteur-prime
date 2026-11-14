# ADR-0010 — Comic Vision : détection locale des cases, texte par fournisseur IA sous budget

- Statut : Accepté
- Date : 2026-11-14

## Contexte

La phase 3 doit repérer les cases, leur ordre de lecture, le texte (bulles, récitatifs,
onomatopées) et, si possible, le locuteur — avec traçabilité, sans dépense non autorisée et
sans dépendre d'un fournisseur unique.

## Décision

1. **Cases : détecteur local, gratuit et déterministe** (`xycut-2`) : découpage récursif le long
   des gouttières, redressement automatique des scans inclinés (seuil de gain calibré par mesure),
   ordre de lecture LTR (comics) ou RTL (manga).
2. **Texte, type de texte et locuteur : fournisseur de vision** derrière l'interface
   `PageVisionProvider` (ADR-0005). Premier adaptateur : Claude (`claude-opus-5-5`, effort
   `medium`, sortie JSON contrainte par schéma, repli serveur en cas de refus). Le prompt est
   versionné (`vision.page_text@1.0.0`) et interdit d'inventer un locuteur à partir de
   connaissances extérieures à la page.
3. **Rattachement géométrique** des textes aux cases (≥ 50 % de recouvrement) et ordre de
   lecture global du texte.
4. **Supervision des coûts** : estimation avant lancement, refus si elle dépasse le budget
   explicite, budget revérifié avant chaque appel à partir des coûts enregistrés, une analyse
   identique (même rendu, détecteur, fournisseur, modèle, prompt, sens) jamais payée deux fois.
5. **Analyses en ajout seul**, rattachées à l'empreinte du rendu : une page au rendu identique
   (autre fichier du même comic) réutilise l'analyse.

## Alternatives considérées

- OpenCV / modèles de détection de cases entraînés : dépendance lourde ou entraînement requis ;
  à réévaluer si le banc d'essai sur vrais comics montre des lacunes.
- OCR classique (Tesseract, Cloud Vision) : mauvais sur le lettrage manuscrit des comics et ne
  classe pas le texte ni le locuteur ; peut être ajouté comme adaptateur de comparaison.

## Conséquences

Mesures synthétiques (200 pages) : F1 = 1,000 et ordre 100 % (pages droites, bruitées, JPEG,
inclinées jusqu'à 1,5°) ; F1 = 0,62 quand une bulle chevauche une gouttière — limite connue,
documentée et testée. Le choix définitif du fournisseur de texte attend le banc d'essai sur un
corpus réel annoté (statut BLOCKED : corpus et budget à fournir par le propriétaire).
