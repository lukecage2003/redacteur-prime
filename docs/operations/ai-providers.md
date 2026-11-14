# Fournisseurs IA — registre de conformité

Aucun fournisseur réel n'est activé. Avant activation, compléter une ligne après vérification
des conditions en vigueur.

| Fournisseur | Usage | Région de traitement | Rétention | Entraînement sur nos données | Vérifié le | Décision |
|---|---|---|---|---|---|---|
| `fake` | CI, tests | local | aucune | non | 2026-11-14 | actif (CI uniquement) |
| `human` | Transcription saisie par le propriétaire | local | base locale | non | 2026-11-14 | actif (gratuit, fait foi) |
| `ollama` embeddings (`nomic-embed-text`) | Knowledge : recherche sémantique | sur la machine de l'utilisateur | aucune hors machine | non | — | implémenté, gratuit, optionnel (`PRIMESTONE_EMBEDDER=ollama`) |
| `ollama` (modèle open source local, ex. `qwen2.5vl:7b`) | Vision : transcription, type, locuteur | **sur la machine de l'utilisateur** | aucune hors machine | non | — | implémenté, gratuit ; vérifier la licence du modèle choisi |
| `claude` (Anthropic, `claude-opus-5-5`) | Vision : transcription, type de texte, locuteur | à vérifier (API Anthropic) | à vérifier dans les conditions en vigueur | à vérifier | — | **implémenté, non activé** : clé API, budget et vérification des conditions requis |

Règles : envoyer le minimum (une page ou une case), jamais de données personnelles de tiers,
budget par mission, résultats mis en cache par `(sha256, page, prompt_version)`.
