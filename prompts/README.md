# Prompts versionnés

Un prompt = un fichier `prompts/<module>/<prompt_id>/<version>.md` (SemVer), avec en-tête :
objectif, entrées attendues, schéma de sortie, limites, langue. Toute modification de fond
crée une nouvelle version ; l'ancienne reste pour la traçabilité (`agent_run.prompt_version`).
Aucun prompt n'existe encore (phase 3+).
