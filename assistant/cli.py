"""Command-line interface: chat in the terminal, morning brief, Google login,
and the web interface for the phone (`python -m assistant web`)."""

import sys
from pathlib import Path

import anthropic

from .agent import Agent
from .app import api_error_message, build_agent, connect_google, open_database
from .config import load_config
from .pricing import cost_usd
from .services.bugs import image_type
from .services.household import user_data
from .services.products import CATALOG_FILE


def confirm_in_terminal(question: str) -> bool:
    answer = input(f"  ⚠ {question} [y/N] ").strip().lower()
    return answer in {"y", "yes", "o", "oui"}


BRIEF_PROMPT = """Morning brief. In a few short lines:
1. today's calendar events;
2. unread emails from the last 24 hours that look important or need an \
answer (ignore newsletters and ads);
3. to-do tasks due today or overdue.
Do not change anything."""


def login(cfg) -> None:
    """Log in to Google in the browser once; the token is saved for later runs."""
    calendar, _ = connect_google(cfg, interactive=True)
    if calendar:
        print(f"Google connected. Token saved in {cfg.google_token_path}")


def bugs(cfg, args: list[str]) -> None:
    """bugs: the open ones. bugs closed: the fixed ones. bugs fix 3 / bugs reopen 3."""
    conn, owner = open_database(cfg)
    reports = user_data(conn, owner).bugs
    if len(args) == 2 and args[0] in ("fix", "reopen") and args[1].isdigit():
        status = "fixed" if args[0] == "fix" else "open"
        ok = reports.set_status(int(args[1]), status)
        return print(f"Bug {args[1]}: {status}." if ok else f"No bug {args[1]}.")
    if args not in ([], ["closed"]):
        sys.exit("Usage: python -m assistant bugs [closed | fix ID | reopen ID]")
    shown = reports.list("fixed" if args == ["closed"] else "open")
    if not shown:
        return print("No bug. 🎉" if not args else "No fixed bug yet.")
    for bug in shown:
        print(f"\n#{bug['id']}  {bug['created_at']}  {bug['reported_by']}  "
              f"[{bug['place']}]  code {bug['version'] or '?'}")
        print(f"  {bug['description']}")
        for line in (bug["details"] or "").splitlines():
            print(f"    {line}")
        if bug["has_image"]:
            print(f"  📎 {save_bug_image(cfg, reports, bug['id'])}")


def save_bug_image(cfg, reports, bug_id: int) -> Path:
    """Write a bug's screenshot next to the data (only you can read it) and
    return its path, to open it."""
    image = reports.image(bug_id)
    folder = cfg.data_dir / "bug_images"
    folder.mkdir(mode=0o700, exist_ok=True)
    path = folder / f"bug-{bug_id}.{image_type(image)}"
    path.write_bytes(image)
    path.chmod(0o600)
    return path


def products(cfg, args: list[str]) -> None:
    """products: requests for new products, and products to fix.
    products done 3: request 3 is handled (added to assistant/data/products.toml)."""
    conn, owner = open_database(cfg)  # also syncs the catalog file
    catalog = user_data(conn, owner).products
    if len(args) == 2 and args[0] == "done" and args[1].isdigit():
        ok = catalog.close_request(int(args[1]))
        return print(f"Request {args[1]}: done." if ok else f"No request {args[1]}.")
    if args:
        sys.exit("Usage: python -m assistant products [done ID]")
    print(f"{len(catalog.names())} products in {CATALOG_FILE}")
    requests = catalog.requests()
    print(f"\nRequests ({len(requests)}):" if requests else "\nNo request.")
    for r in requests:
        print(f"  #{r['id']}  {r['name']}  ({r['requested_by']}, {r['created_at']})")
    retired = catalog.retired_in_use()
    print("\nNot in the file but still used (add them, or change the recipes):"
          if retired else "\nEvery product in use is in the file.")
    for p in retired:
        where = [f"recipes: {p['recipes']}"] if p["recipes"] else []
        where += [f"{p['on_list']} on the shopping list"] if p["on_list"] else []
        print(f"  {p['name']}  ({', '.join(where)})")


def main() -> None:
    cfg = load_config()
    args = sys.argv[1:]
    if args == ["login"]:
        return login(cfg)
    if args[:1] == ["bugs"]:
        return bugs(cfg, args[1:])
    if args[:1] == ["products"]:
        return products(cfg, args[1:])
    if args not in ([], ["brief"], ["web"]):
        sys.exit("Usage: python -m assistant [login | brief | web | bugs | products]")

    calendar, gmail = connect_google(cfg, interactive=False)

    if args == ["web"]:
        from .web.server import serve  # imported here: the CLI doesn't need it
        return serve(cfg, calendar, gmail)

    _, owner = open_database(cfg)  # the terminal acts as the owner
    agent = build_agent(cfg, confirm_in_terminal, owner, calendar, gmail)
    if args == ["brief"]:  # one question, then exit (later: run by cron)
        ask_and_print(agent, BRIEF_PROMPT)
    else:
        chat(agent, cfg.model)
    cost = cost_usd(cfg.model, agent.input_tokens, agent.output_tokens,
                    agent.cache_read_tokens, agent.cache_write_tokens)
    print(f"\nTokens: {agent.input_tokens} in (+{agent.cache_read_tokens} read from cache, "
          f"{agent.cache_write_tokens} written to cache), {agent.output_tokens} out"
          + (f" · ${cost:.4f}" if cost is not None else ""))


def chat(agent: Agent, model: str) -> None:
    print(f"assistant ({model}) — empty line or Ctrl-D to quit")
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text or not ask_and_print(agent, text):
            break


def ask_and_print(agent: Agent, text: str) -> bool:
    """Ask the agent and print the answer. Return False if we should stop."""
    try:
        print(agent.ask(text))
    except anthropic.APIError as e:
        print(api_error_message(e))
        return not isinstance(e, anthropic.AuthenticationError)
    return True


if __name__ == "__main__":
    main()
