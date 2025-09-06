# Ensure tests prefer the local python-sdk repository over any installed site-packages
# This helps when running pytest directly (outside tox/CI), so changes in the repo are exercised.
from __future__ import annotations

import sys
from pathlib import Path
import importlib


def pytest_configure(config):  # noqa: D401 (pytest hook)
    """Pytest configuration hook that prepends the repo root to sys.path.

    This ensures `import dapr` resolves to the local source tree when running tests directly.
    Under tox/CI (editable installs), this is a no-op but still safe.
    """
    try:
        # ext/dapr-ext-workflow/tests/conftest.py -> repo root is 3 parents up
        repo_root = Path(__file__).resolve().parents[3]
    except Exception:
        return

    repo_str = str(repo_root)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)

    # Best-effort diagnostic: show where dapr was imported from
    try:
        dapr_mod = importlib.import_module("dapr")
        dapr_path = Path(getattr(dapr_mod, "__file__", "<unknown>")).resolve()
        where = "site-packages" if "site-packages" in str(dapr_path) else "local-repo"
        print(f"[dapr-ext-workflow/tests] dapr resolved from {where}: {dapr_path}", file=sys.stderr)
    except Exception:
        # If dapr isn't importable yet, that's fine; tests importing it later will use modified sys.path
        pass
