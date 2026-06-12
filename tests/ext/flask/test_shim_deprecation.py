"""Locks the deprecation contract of the top-level `flask_dapr` shim.

The shim re-exports `dapr.ext.flask` and must emit a `FutureWarning` on import,
not a `DeprecationWarning` (which Python's default filter would suppress for
non-`__main__` callers).
"""

# TODO: remove in 1.22 with the flask_dapr shim.

import sys

import pytest


def _fresh_import():
    sys.modules.pop('flask_dapr', None)
    import flask_dapr

    return flask_dapr


def test_emits_future_warning_on_import():
    with pytest.warns(FutureWarning, match=r'dapr\.ext\.flask'):
        _fresh_import()


def test_reexports_public_surface(recwarn):
    flask_dapr = _fresh_import()
    from dapr.ext.flask import DaprActor, DaprApp

    assert flask_dapr.DaprActor is DaprActor
    assert flask_dapr.DaprApp is DaprApp
