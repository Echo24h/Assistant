# Plan du projet : assistant personnel (agent IA)

Décisions prises le 10.11.2026. Document interne (en français, pour moi).

## Deux objectifs

1. **Alléger mon organisation** : agenda, mails, todo list, entraînement
   sportif.
2. **Combler mon écart principal pour les stages en IA agentique**
   (Nestlé, Lombard Odier...) : montrer que je sais **écrire moi-même la
   boucle d'un agent** (appel d'outils, gestion des erreurs, évaluation
   chiffrée), pas seulement utiliser Claude Code.

## Agent ou skill ?

- **Agent** : un LLM qui tourne en boucle avec des outils. Il reçoit un
  objectif, choisit une action, regarde le résultat, recommence jusqu'au
  but. Claude Code est un agent.
- **Skill** : un fichier d'instructions (plus des scripts) qu'un agent
  charge quand la tâche correspond. Il ne fait rien tout seul.
- Ce que j'ai déjà fait : des skills pour un agent existant. Ce que ce
  projet ajoute : **construire l'agent lui-même**.
- Phrase d'entretien : « I've built skills and workflows on top of an
  existing agent, Claude Code. I then wrote my own agent loop with the
  API, to understand what happens underneath. »

## Choix techniques

- **Python, pas n8n** : n8n montre qu'on sait utiliser un outil ; du code
  montre la boucle, les outils, les erreurs, l'évaluation. Et un agent qui
  décide selon la situation se code mieux qu'il ne se dessine en cases.
- **MCP** (Model Context Protocol) pour Gmail et Google Calendar : ne pas
  recoder OAuth et les API Google, utiliser des serveurs MCP existants.
- **Mes propres outils** pour la todo list et l'entraînement : fonctions
  Python (ou petit serveur MCP), stockage SQLite local.

## Modèles (API Claude)

- **Sonnet 5.5** (`claude-sonnet-5-5`) pour l'agent principal : bon en
  appels d'outils, coût raisonnable.
- **Haiku 5.5** (`claude-haiku-5-5`) pour les tâches simples et
  répétées : tri des mails, classement, extraction de dates.
- Pas besoin d'Opus.
- *Model routing* : choisir le modèle selon la tâche (point d'entretien).
- Option plus tard : modèle local (Ollama, Qwen ou Llama) pour du tri
  très sensible ; moins fiable pour enchaîner des outils.
- Vérifier les prix actuels sur la page tarifs d'Anthropic.

## Coûts

- **Abonnement Claude (Pro)** : couvre claude.ai et Claude Code, **pas
  l'API**. Utile tout de suite pour ma vie quotidienne : autoriser les
  connecteurs Gmail et Google Calendar dans claude.ai (sans coder).
- **API** : facturée à l'usage, **prépayée**.
  - Charger 10 $ de crédits, **rechargement automatique désactivé**.
  - Fixer une **limite mensuelle de dépenses** dans la console.
  - Perte maximale : ce qui est chargé. Usage personnel estimé : quelques
    dollars par mois.

## Hébergement

1. **Au début : en local**, sur mon PC Linux, lancé en ligne de commande.
2. **Ensuite, s'il doit tourner seul** (brief du matin, rappels) :
   Raspberry Pi à la maison, ou petit VPS (Infomaniak en Suisse, Hetzner
   en Allemagne).
3. **Aucun port ouvert** : `cron` + notifications (Telegram, ntfy, ou un
   mail à moi-même). Accès à distance par **Tailscale** si besoin.

## Sécurité

### 1. Secrets
- Clé d'API et jetons Google dans `.env` (dans `.gitignore`, droits
  `600`), jamais dans le dépôt.
- **gitleaks** en pre-commit pour bloquer une clé commitée par erreur.
- Plafond de dépenses dans la console Anthropic.

### 2. Permissions Google minimales
- Début : `gmail.readonly`, `calendar.readonly`.
- Plus tard : `gmail.compose` (brouillons). **Jamais `gmail.send`.**
- Projet Google Cloud en mode « test », moi seul comme utilisateur.

### 3. L'agent : la *lethal trifecta* (Simon Willison)
Un agent devient dangereux s'il réunit les trois :
1. accès à des **données privées** (mes mails) ;
2. lecture de **contenu écrit par des inconnus** (ces mêmes mails) ;
3. un **moyen d'envoyer des données dehors** (envoyer un mail, ouvrir
   une URL).

Règle : **ne jamais donner le troisième** à l'agent qui lit mes mails.
- Pas d'envoi de mail, pas de navigation web libre.
- Actions sensibles (créer un événement, rédiger un brouillon) : **ma
  confirmation, imposée dans le code** (un `if`), pas dans le prompt.
- Liste explicite des outils autorisés.
- Journal local de tous les appels d'outils.

### 4. Données
- Ne pas stocker le contenu des mails : seulement résumés et tâches.
- Données sportives et de santé : SQLite local, sauvegardes chiffrées.
- Dépôt GitHub public : **code + faux mails de test uniquement**. Les
  vraies données vivent hors du dépôt (`~/.local/share/assistant/`).
- Serveur : SSH par clé uniquement, pare-feu, mises à jour automatiques.

## Évaluation (ce qui en fait un projet portfolio)

- Jeu de test d'environ **50 faux mails** : réunion, facture, spam,
  demande urgente, newsletter, **tentatives d'injection de prompt**.
- Mesures :
  - tri : catégorie correcte (précision, rappel par catégorie) ;
  - extraction : dates et tâches correctes ;
  - sécurité : part des injections ignorées (l'agent n'appelle aucun outil
    demandé par le mail).
- Résultats chiffrés dans le README, script `evals/run.py` reproductible.

## Feuille de route

- **Jour 1** (local, sans Google) : boucle de l'agent avec l'API (Sonnet),
  outils todo et entraînement sur SQLite, interface en ligne de commande.
  Déjà utile, aucun risque.
- **Jour 2** : Gmail et Calendar en lecture seule (MCP), « brief du
  matin » (agenda du jour, mails importants, tâches).
- **Jour 3** : faux mails, évaluation chiffrée, README avec résultats.
- **Plus tard** : brouillons de réponse et création d'événements avec
  confirmation ; Haiku pour le tri ; serveur + cron + notifications.

## Avant de commencer

- [ ] Créer une clé d'API sur console.anthropic.com, charger 10 $,
      désactiver le rechargement, fixer une limite mensuelle.
- [ ] Copier `.env.example` en `.env`, y mettre la clé.
- [ ] `python3 -m venv .venv && . .venv/bin/activate`
- [ ] (Jour 2) Créer un projet Google Cloud en mode test, activer les API
      Gmail et Calendar, scopes en lecture seule.
- [ ] Dépôt GitHub public : seulement quand gitleaks est en place.
- [ ] En parallèle, pour la vie quotidienne : autoriser les connecteurs
      Gmail et Google Calendar dans claude.ai.
