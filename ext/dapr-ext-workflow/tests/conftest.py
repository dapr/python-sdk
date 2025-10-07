"""
Copyright 2025 The Dapr Authors
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

# Ensure tests prefer the local python-sdk repository over any installed site-packages
# This helps when running pytest directly (outside tox/CI), so changes in the repo are exercised.
from __future__ import annotations  # noqa: I001

import sys
from pathlib import Path
import importlib
import pytest


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
        dapr_mod = importlib.import_module('dapr')
        dapr_path = Path(getattr(dapr_mod, '__file__', '<unknown>')).resolve()
        where = 'site-packages' if 'site-packages' in str(dapr_path) else 'local-repo'
        print(f'[dapr-ext-workflow/tests] dapr resolved from {where}: {dapr_path}', file=sys.stderr)
    except Exception:
        # If dapr isn't importable yet, that's fine; tests importing it later will use modified sys.path
        pass


@pytest.fixture(autouse=True)
def cleanup_workflow_registrations(request):
    """Clean up workflow/activity registration markers after each test.

    This prevents test interference when the same function objects are reused across tests.
    The workflow runtime marks functions with _dapr_alternate_name and _activity_registered
    attributes, which can cause 'already registered' errors in subsequent tests.
    """
    yield  # Run the test

    # After test completes, clean up functions defined in the test module
    test_module = sys.modules.get(request.module.__name__)
    if test_module:
        for name in dir(test_module):
            obj = getattr(test_module, name, None)
            if callable(obj) and hasattr(obj, '__dict__'):
                try:
                    # Only clean up if __dict__ is writable (not mappingproxy)
                    if isinstance(obj.__dict__, dict):
                        obj.__dict__.pop('_dapr_alternate_name', None)
                        obj.__dict__.pop('_activity_registered', None)
                except (AttributeError, TypeError):
                    # Skip objects with read-only __dict__
                    pass
