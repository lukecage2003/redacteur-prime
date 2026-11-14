# ADR-0005 — Passerelle IA indépendante des fournisseurs

- Statut : Accepté
- Date : 2026-11-14

## Décision

Le code métier n'appelle que `primestone.ai_gateway.AIGateway`. Chaque fournisseur est un
adaptateur implémentant un protocole (`LLMProvider` aujourd'hui ; vision, OCR, embeddings, STT,
TTS ensuite). La passerelle :

- contrôle le budget **avant** l'appel (estimation) et cumule le coût réel ;
- trace chaque appel : fournisseur, modèle, `prompt_id`, `prompt_version`, jetons, coût,
  latence, erreur ;
- fournit `FakeLLMProvider`, déterministe et gratuit, seul autorisé en CI.

Les prompts sont versionnés dans `prompts/` et référencés par identifiant + version.

## Alternatives considérées

- SDK fournisseur direct : verrouillage, pas de budget ni de traçabilité uniformes.
- Bibliothèque d'abstraction tierce (LiteLLM, LangChain) : réévaluée lors de l'ajout des
  premiers fournisseurs réels (phase 3) ; elle pourrait servir d'implémentation d'adaptateur
  sans changer l'interface métier.

## Conséquences

Changer de fournisseur = ajouter un adaptateur + benchmark. Les comparaisons de fournisseurs
utilisent le même corpus et la même interface.
