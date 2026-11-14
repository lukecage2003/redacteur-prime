# ADR-0013 — Editorial Director : missions durables, agents déterministes, Fact Checker bloquant

- Statut : Accepté
- Date : 2026-11-14

## Décision

1. **Chief Editor = machine à états persistée** (`mission`, `mission_task`), exécutée par une
   étape durable de la file (ADR-0004) : PLANNED → RUNNING → AWAITING_APPROVAL → APPROVED |
   REJECTED, ou FAILED. Reprise après interruption sans rejouer les tâches réussies.
2. **Plan par type de mission** (Research Director) : dossier de personnage, audit de
   continuité, vérification d'un texte. Chaque tâche a un agent, des entrées structurées et un
   caractère critique ou non.
3. **Gestion des échecs** : deux tentatives par tâche ; échec non critique ⇒ livrable dégradé et
   signalé ; échec critique ⇒ mission FAILED, tâches restantes SKIPPED, aucune approbation.
4. **Agents disponibles déterministes et gratuits** (Research Director, Comics Analyst,
   Continuity Editor, Character Researcher, Fact Checker, rédaction par gabarit). Les agents
   des phases suivantes sont listés avec leur phase et ne sont jamais simulés.
5. **Fact Checker bloquant** : chaque citation « … » est recherchée dans la transcription servie
   de la page (et de la case) qu'elle cite ; âges contredits par les affirmations de l'œuvre,
   références invalides et citations introuvables sont des erreurs majeures. Un livrable en
   erreur majeure **ne peut pas être approuvé** (refus côté service et API). Les dossiers du
   Chief Editor passent par le même contrôle.
6. **Rédaction par modèle facultative et gratuite** (Ollama local, via `ai_gateway` en mode zéro
   coût) : le texte du modèle n'est retenu que s'il passe le Fact Checker avec au moins autant de
   citations vérifiées que le gabarit ; sinon le gabarit est conservé et le rejet est tracé
   (`agent_run`).
7. **Décision humaine** obligatoire (`approval_request`), journalisée.

## Conséquences

Autonomie L5 supervisée à coût nul : le système planifie, exécute, vérifie et recommande ; l'humain
décide. Limites : pas de résolution des pronoms ni de vérification sémantique des paraphrases
(signalées PARAPHRASE pour relecture humaine).
