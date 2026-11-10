"""Command-line interface: a simple chat loop in the terminal."""

import anthropic

from .agent import Agent
from .config import load_config
from .store import Store
from .tools import ToolBox


def confirm_in_terminal(question: str) -> bool:
    answer = input(f"  ⚠ {question} [y/N] ").strip().lower()
    return answer in {"y", "yes", "o", "oui"}


def main() -> None:
    cfg = load_config()
    store = Store(cfg.db_path)
    agent = Agent(
        client=anthropic.Anthropic(),  # reads ANTHROPIC_API_KEY from the environment
        toolbox=ToolBox(store, confirm=confirm_in_terminal),
        model=cfg.model,
        effort=cfg.effort,
        log_path=cfg.log_path,
    )
    print(f"assistant ({cfg.model}) — empty line or Ctrl-D to quit")

    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            break
        try:
            print(agent.ask(text))
        except anthropic.AuthenticationError:
            print("Invalid or missing ANTHROPIC_API_KEY (see .env.example).")
            break
        except anthropic.RateLimitError:
            print("Rate limited, try again in a moment.")
        except anthropic.APIStatusError as e:
            print(f"API error {e.status_code}: {e.message}")
        except anthropic.APIConnectionError:
            print("Network error: cannot reach the API.")

    print(f"\nTokens used: {agent.input_tokens} in, {agent.output_tokens} out")


if __name__ == "__main__":
    main()
