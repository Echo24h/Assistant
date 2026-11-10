"""Which code is running: the git commit, saved with each bug report."""

import subprocess
from functools import cache
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


@cache  # asked once per run: the code does not change while it runs
def code_version() -> str | None:
    """"5263066", plus "+changes" if files were edited since; None without git."""
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                                capture_output=True, text=True, timeout=5, check=True)
        changes = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                                 cwd=REPO, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return commit.stdout.strip() + ("+changes" if changes.stdout.strip() else "")
