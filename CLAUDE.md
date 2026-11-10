# Instructions pour Claude Code (projet assistant)

Contexte et décisions : lire `docs/PLAN.md` avant toute modification.

## Règles

- Grégory doit pouvoir **expliquer chaque ligne** en entretien : code
  simple, boucle d'agent écrite à la main, pas de framework d'agents
  (LangChain, etc.) sans qu'il le demande.
- Sécurité non négociable :
  - jamais d'outil qui envoie un mail ou des données vers l'extérieur ;
  - scopes Google en lecture seule (puis `gmail.compose` au plus) ;
  - confirmation des actions sensibles **dans le code** ;
  - aucun secret ni donnée personnelle dans le dépôt (`.env`, données
    dans `~/.local/share/assistant/`) ; faux mails seulement dans `evals/`.
- Modèles : `claude-sonnet-5-5` pour l'agent, `claude-haiku-5-5` pour le
  tri ; noms dans la config, pas en dur partout.
- Code et README en anglais (dépôt public) ; `docs/PLAN.md` en français.
- Commiter ou pousser seulement si Grégory le demande.
