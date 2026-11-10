# Household mode

The assistant can be shared by the people living together (here: a
couple). Each person has their own conversation with the agent; the
household shares a to-do list, recipes, a shopping list and a budget.
Personal accounts (Google Calendar, Gmail) stay with their owner.

Setup steps (Tailscale sharing, `.env`): [INSTALL.md](INSTALL.md#add-a-person-to-the-household).

## Who is who

- The household is the list `ASSISTANT_WEB_USERS` in `.env`
  (`login=name`, comma-separated). The database follows it at start
  (`users` table); nobody is ever deleted, because tasks and expenses
  refer to them.
- **The first person is the owner**: the Google accounts connected with
  `python -m assistant login` are theirs, and the terminal acts in their
  name.
- A request is identified by the `Tailscale-User-Login` header, set by
  Tailscale itself. A login that is not in the list gets HTTP 403.
- The other person uses Tailscale **machine sharing**: they keep their own
  Tailscale account and see only the assistant's machine, not the owner's
  other devices.

## Who sees what

| | Owner | Other person |
|---|---|---|
| Chat with the agent | ✅ own conversation | ✅ own conversation |
| To-do list | shared tasks + own 🔒 tasks | shared tasks + own 🔒 tasks |
| Recipes | ✅ shared | ✅ shared |
| Shopping list | ✅ shared | ✅ shared |
| Budget (expenses, who owes whom) | ✅ shared | ✅ shared |
| Google Calendar | ✅ | ❌ |
| Gmail (read-only) | ✅ | ❌ |

- **Tasks are shared by default.** A task marked 🔒 (in the Tasks tab, or
  "private" in the chat, e.g. a surprise for the other person) is
  invisible to the others, and cannot be changed by them even with its
  id: the filter is in every SQL query (`services/tasks.py`).
- **Google is owner-only, enforced in code**: the web server gives the
  calendar and Gmail tools to the owner's agent only
  (`web/server.py`, `App.session`). The other person's agent does not
  even know these tools exist.

## What the household can do

**In the chat** (the agent, costs tokens): everything below in plain
language. Examples:

- "Ajoute payer le loyer pour le 1er, urgent"
- "Propose-moi un plat avec des courgettes", then "garde-la"
- "Ajoute les lasagnes aux courses pour 4"
- "J'ai payé 80 CHF de courses" / "Anna m'a remboursé 45 CHF"
- "Qui doit combien ?"

**In the tabs** (no model, 0 tokens, instant):

- **Tâches**: add, tick, priority (tap the badge), 👥/🔒 to share or not.
- **Recettes**: import from a link, type one in, send to the shopping list
  for N people.
- **Courses**: type "2 l de lait", tick in the shop, remove what is ticked.
- **Budget**: who owes whom at the top, add an expense, the month's list
  and totals per category.

**Report a bug**: the 🐞 button (any tab) or "signale un bug : …" in the
chat. The report keeps the tab, the last error, the code version and, if
the person agrees, the last chat messages and a screenshot (made smaller
and re-encoded in the browser, which drops the photo's metadata such as
GPS position; checked as a real JPEG/PNG on the server, never served back
by the web page). It stays on the server (no
GitHub issue: that would be a way out to the internet); the owner reads
it with `python -m assistant bugs` and closes it with `bugs fix ID`.

## How shared data works

- **Shopping list**: a recipe is scaled to the number of people, and the
  same item (same name, same unit, not yet ticked) is added up instead of
  repeated. Units are normalized (kg → g, cl → ml…) so that they can be
  added.
- **Expenses**: each expense has a payer and shares that add up to the
  amount, in integer cents. *Equal* splits it between everyone (a cent
  left over goes to the payer); *for the other* puts it all on the other
  person, which is also how a repayment is recorded. Balance = what you
  paid − your shares; the household total is always 0. "Who owes whom"
  is computed from the balances, for any number of people.
- **Confirmations**: when the agent wants to save or delete a recipe, add
  or delete an expense, delete a task or change the calendar, the person
  talking to it confirms with ✅ / ❌. A click in a tab is already a
  decision, so tabs do not ask again (except before deleting a task, a
  recipe or an expense).

## Limits

- Everyone in the household can change and delete shared data (tasks,
  recipes, shopping list, expenses). It is designed for people who trust
  each other.
- No bank connection: expenses are entered by hand.
- One owner for Google: the other person cannot connect their own
  calendar (yet).
