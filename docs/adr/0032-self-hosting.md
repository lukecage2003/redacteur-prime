# ADR-0032 — Auto-hébergement gratuit (Oracle Always Free + Tailscale)

- Statut : Accepté
- Date : 2026-11-15

## Contexte

Le propriétaire veut un accès en ligne permanent, gratuit et personnel. Google Cloud
(ADR-0003, phase 13) reste la cible « production » mais n'est pas gratuit (Cloud SQL, accès
IAP). L'abonnement Google AI Pro ne fournit pas d'hébergement.

## Décision

1. Nouvel environnement `selfhosted` : base PostgreSQL locale avec mot de passe dédié
   (obligatoire), stockage sur disque persistant, vision par Ollama (jamais « fake »), IAP
   non requis.
2. `deploy/selfhost/docker-compose.yml` : base, migration (service ponctuel), API, worker, web,
   Ollama, Caddy, sauvegarde quotidienne. Images officielles multi-architecture (ARM).
3. Accès : aucun port public. Caddy n'écoute que sur 127.0.0.1 ; `tailscale serve` fournit
   HTTPS sur le réseau privé du propriétaire ; Caddy exige en plus un mot de passe (bcrypt).
   `tailscale funnel` (public) est proscrit.
4. Cible recommandée : Oracle Cloud VM.Standard.A1.Flex « Always Free » (4 OCPU, 24 Go).

## Conséquences

- Coût nul dans les limites « Always Free » ; risque de récupération d'une instance
  inactive : sauvegardes à copier hors de la machine.
- Les workflows GCP restent inchangés et inactifs.
