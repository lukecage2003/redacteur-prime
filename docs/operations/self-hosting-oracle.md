# Auto-hébergement gratuit : Oracle Cloud « Always Free » (usage personnel)

PRIMESTONE complet (base, API, worker, web, modèles locaux) sur **une machine ARM gratuite**
d'Oracle Cloud, accessible **seulement depuis tes appareils** (Tailscale) et protégée par un
mot de passe. Aucune page publique : tes comics restent privés. ADR-0032.

## Ce qui est gratuit, et ses limites

- Oracle « Always Free » : machine **VM.Standard.A1.Flex** (ARM) jusqu'à 4 OCPU et 24 Go de
  RAM au total, 200 Go de disque. Une carte bancaire est demandée à l'inscription (vérification).
- Tailscale : gratuit pour un usage personnel.
- Modèles : Ollama, Piper, whisper.cpp, tous locaux et gratuits.
- **À savoir** :
  - Oracle peut récupérer une instance gratuite jugée inactive (faible usage CPU sur 7 jours) ;
    garde des sauvegardes hors de la machine (section 7).
  - La capacité ARM gratuite est parfois épuisée dans une région : réessaie plus tard ou
    choisis ta région d'origine avec soin (elle est définitive).
  - Ne crée **que** des ressources marquées « Always Free » ; active une alerte budgétaire à
    1 € (section 8) pour être prévenu de toute dépense.

## 1. Créer la machine

1. Crée un compte sur cloud.oracle.com (offre gratuite), choisis ta région d'origine.
2. Compute → Instances → Créer : image **Ubuntu 24.04** (aarch64), forme
   **VM.Standard.A1.Flex**, 4 OCPU / 24 Go, disque de démarrage 150 Go.
3. Ajoute ta clé SSH publique. Ne touche pas au pare-feu (security list) : seul SSH (22)
   est ouvert par défaut, et **aucun autre port ne doit l'être**.

## 2. Préparer le système (en SSH)

```bash
sudo apt-get update && sudo apt-get -y upgrade
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"   # puis se déconnecter / reconnecter
```

## 3. Tailscale (accès privé)

Installe Tailscale sur la machine **et** sur ton PC / téléphone, avec le même compte :

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --ssh
```

Ensuite, tu peux même fermer le port 22 public et te connecter par `ssh` via Tailscale.

## 4. Installer PRIMESTONE

```bash
git clone https://github.com/lukecage2003/redacteur-prime.git
cd redacteur-prime/deploy/selfhost
cp .env.example .env
openssl rand -base64 32   # à coller dans POSTGRES_PASSWORD
docker run --rm caddy:2.10.0 caddy hash-password --plaintext 'ton-mot-de-passe'
nano .env                 # remplir ; doubler chaque « $ » de l'empreinte (« $$ »)
docker compose up -d --build
docker compose ps         # migrate doit finir « Exited (0) », les autres « running »
```

## 5. Ouvrir l'accès (privé, HTTPS)

```bash
sudo tailscale serve --bg http://127.0.0.1:8080
tailscale serve status    # affiche l'adresse https://<machine>.<tailnet>.ts.net
```

Ouvre cette adresse depuis un appareil connecté à Tailscale, puis saisis ton mot de passe.
Ne lance **jamais** `tailscale funnel` : il rendrait le site public.

## 6. Modèles locaux (facultatif, gratuit)

```bash
docker compose exec ollama ollama pull qwen2.5vl:7b      # vision des pages (lent sur CPU)
docker compose exec ollama ollama pull qwen2.5:7b        # rédaction (PRIMESTONE_EDITORIAL_WRITER=ollama)
docker compose exec ollama ollama pull nomic-embed-text  # plongements (PRIMESTONE_EMBEDDER=ollama)
```

Après modification de `.env` : `docker compose up -d`. Pour la voix (Piper, whisper.cpp),
voir docs/modules/voice.md et docs/modules/identity.md.

## 7. Sauvegardes et restauration

- Le service `backup` écrit chaque jour `backups/primestone-*.dump` (14 jours conservés).
- **Copie-les hors de la machine** régulièrement, par exemple depuis ton PC :
  `scp -r <machine>:redacteur-prime/deploy/selfhost/backups ./primestone-backups`.
- Les fichiers importés sont dans le volume `primestone_storage`, les comics restent aussi
  chez toi : garde tes originaux.
- Restauration (base vide) :

```bash
docker compose stop api worker web
docker compose exec -T db pg_restore -U primestone -d primestone --clean --if-exists < backups/primestone-AAAAMMJJ-HHMMSS.dump
docker compose up -d
```

## 8. Garde-fous de coût

- Gouvernance et facturation → Budgets : budget de 1 € avec alerte par e-mail.
- Le mode zéro coût de PRIMESTONE reste actif (`PRIMESTONE_ZERO_COST=true`) : aucun
  fournisseur payant n'est appelé.

## 9. Mettre à jour

```bash
cd redacteur-prime && git pull
cd deploy/selfhost && docker compose up -d --build   # migrate applique les nouvelles migrations
```

Les migrations sont additives ; une sauvegarde est faite chaque jour, en lancer une avant
toute mise à jour importante :
`docker compose exec -T db pg_dump -U primestone -Fc primestone > backups/avant-maj.dump`.

## Sécurité

- Aucun port applicatif exposé : Caddy écoute sur 127.0.0.1, l'accès passe par Tailscale.
- Mot de passe (bcrypt) exigé par Caddy, en plus de Tailscale.
- Secrets uniquement dans `.env` (ignoré par Git), jamais dans le dépôt.
- Journaux JSON sans corps ni paramètres de requête, secrets masqués.
