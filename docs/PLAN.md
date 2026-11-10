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
- **Google Calendar : API Google appelée directement** en Python
  (`google-api-python-client`), décision du 10.11.2026 à la place de MCP :
  je choisis et vérifie le scope moi-même (beaucoup de serveurs MCP
  communautaires demandent l'accès complet), et le code reste court et
  explicable. Google propose aussi un serveur MCP officiel (Calendar MCP
  API) : option pour plus tard, pour montrer MCP en entretien.
- **Gmail : même approche** (API directe, `gmail.readonly`), décidé le
  10.11.2026. Un seul token Google pour les deux scopes
  (`assistant/services/google_auth.py`) ; un token sans le scope Gmail impose un
  nouveau `login`.
  - Contenu des mails marqué `untrusted_email`, corps tronqué à 3000
    caractères, **jamais écrit dans le journal** (`NOT_LOGGED`).
  - Aucun outil d'envoi, de brouillon, de suppression ni de libellé.
- **Mes propres outils** pour la todo list et l'entraînement : fonctions
  Python (ou petit serveur MCP), stockage SQLite local.

## Modèles (API Claude)

Décision du 10.11.2026 : **très petit budget** (5 $ de crédits).

- **Haiku 5.5** (`claude-haiku-5-5`) **par défaut**, pour l'agent comme
  pour le tri, avec l'effort `low`. Environ 20 fois moins cher que Sonnet
  (0,10 $ / 0,50 $ par million de tokens en entrée / sortie) : ~0,07
  centime par question, ~7 000 questions avec 5 $.
- **Sonnet 5.5** (`claude-sonnet-5-5`) seulement là où l'évaluation
  (Jour 3) montre que Haiku ne suffit pas.
- Pas besoin d'Opus.
- Économies : sessions courtes (tout l'historique est renvoyé à chaque
  appel), tests avec le faux client (gratuits).
- *Model routing* : choisir le modèle selon la tâche (point d'entretien),
  **mesuré** : comparer Haiku et Sonnet sur les mêmes faux mails.
- Option plus tard : modèle local (Ollama, Qwen ou Llama) pour du tri
  très sensible ; moins fiable pour enchaîner des outils.
- Vérifier les prix actuels sur la page tarifs d'Anthropic.

## Coûts

- **Abonnement Claude (Pro)** : couvre claude.ai et Claude Code, **pas
  l'API**. Utile tout de suite pour ma vie quotidienne : autoriser les
  connecteurs Gmail et Google Calendar dans claude.ai (sans coder).
- **API** : facturée à l'usage, **prépayée**.
  - Charger 5 $ de crédits (valables 1 an), **rechargement automatique
    désactivé**.
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
- Agenda : `calendar.events` (lire **et modifier** les événements),
  décision du 10.11.2026 pour un usage quotidien. **Pas `calendar`** :
  il permet aussi de partager l'agenda (fuite possible).
  - **Jamais d'invités** et toujours `sendUpdates="none"` : ajouter un
    invité envoie un mail, donc un canal de sortie (trifecta).
  - Création, modification, suppression : confirmation imposée dans le
    code. Lecture : libre.
- Gmail : `gmail.readonly`.
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

## Architecture en trois couches (10.11.2026)

- `services/` : le cœur (SQLite, Google), sans IA ni web.
- `agent/` : la boucle et les outils, **un fichier par domaine** (tâches,
  agenda, Gmail) ; `agent/tools/__init__.py` = liste autorisée et
  confirmations. Plus tard, les domaines donnés au ToolBox dépendront de
  la personne qui parle.
- `web/` : la plateforme. Elle appelle **directement** `services/` pour ce
  qui n'a pas besoin du modèle (voir/cocher la todo, l'agenda) : 0 token,
  instantané. Les confirmations ✅ / ❌ ne concernent que les décisions du
  modèle ; un clic de l'utilisateur est déjà sa décision. Identité et
  CSRF s'appliquent à toutes les routes.

## Téléphone (décidé le 10.11.2026)

- **Page web privée via Tailscale**, pas Telegram (Telegram lit les
  messages des bots, pas de chiffrement de bout en bout) ni Signal (trop
  complexe). `python -m assistant web` : bibliothèque standard Python,
  écoute sur `127.0.0.1` seulement ; `tailscale serve` l'expose en HTTPS
  à mes appareils uniquement. Aucun port ouvert.
- **Identité** : en-tête `Tailscale-User-Login`, accepté seulement si le
  login est dans `ASSISTANT_WEB_USERS`. Pas d'en-tête = refus.
- **CSRF** : corps JSON obligatoire (impose un preflight CORS jamais
  autorisé) et vérification de l'en-tête `Origin`.
- **Confirmations** : boutons ✅ / ❌. L'agent tourne dans un thread qui
  attend la réponse dans une file (`queue`) ; sans réponse en 5 min = non.
- Les réponses sont insérées comme texte (`textContent`), jamais en HTML :
  un mail piégé ne peut pas injecter de code dans la page.

### Plus tard : ma copine
- Partage de la seule machine de l'assistant (*node sharing*) ou
  invitation dans le tailnet. **À vérifier** : Tailscale ne transmet
  peut-être pas l'identité pour une machine partagée ; sinon l'inviter
  comme utilisateur du tailnet.
- **Outils autorisés selon la personne, imposés dans le code** : tâches
  communes, finances du couple pour nous deux ; mon Gmail, mon agenda et
  mes tâches perso pour moi seul.
- Courses : plutôt un **outil recettes** qui propose une liste de courses
  (à concevoir plus tard).
- Finances : **saisie manuelle** d'abord (qui a payé quoi, qui doit
  combien). Connexion bancaire : non pour l'instant (gros accès en plus,
  et l'agent lit des mails écrits par des inconnus).

### Migration vers un serveur
- Code par `git clone`, `.env` par `scp`, données par `rsync`
  (`~/.local/share/assistant/`) ; service `deploy/assistant-web.service`.
- Tailscale avec `--ssh` : SSH sans port ouvert, pare-feu fermé en entrée.
- Avant : **passer l'application Google en production** (sinon le token
  expire tous les 7 jours) ; faire `login` sur le PC et copier `token.json`.
- VPS (Infomaniak, Suisse) : toujours en ligne, mais l'hébergeur peut
  accéder au disque. Raspberry Pi : les données restent à la maison.

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

- **Jour 1** (local, sans Google) : boucle de l'agent avec l'API (Haiku),
  outils todo et entraînement sur SQLite, interface en ligne de commande.
  Déjà utile, aucun risque.
- **Jour 2** : Calendar (lecture + écriture confirmée), Gmail en lecture
  seule, « brief du
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
      Gmail et Calendar, scopes `calendar.events` et `gmail.readonly`.
- [ ] Dépôt GitHub public : seulement quand gitleaks est en place.
- [ ] En parallèle, pour la vie quotidienne : autoriser les connecteurs
      Gmail et Google Calendar dans claude.ai.
