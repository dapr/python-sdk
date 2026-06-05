# -*- coding: utf-8 -*-

"""
Copyright 2026 The Dapr Authors
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

# TODO: remove in 1.20 (pre-1.19 dapr-ext-* / flask-dapr migration only).
#
# On import, checks for two states a legacy dapr-ext-* install could leave
# the environment in.
#
# 1. Legacy `dapr-ext-*` or `flask-dapr` dist still installed alongside
#    core dapr.
#    Pre-1.19 each extension was its own dist owning files under
#    `dapr/ext/<name>/`, the new core wheel ships those same files.
#    pip has no cross-dist ownership awareness, so `pip uninstall <legacy>`
#    walks the legacy RECORD and deletes `dapr/ext/<name>/*.py` from disk. End
#    state: `pip show dapr` reports OK, but `from dapr.ext.<name> import ...`
#    raises ModuleNotFoundError.
#
# 2. Legacy already uninstalled with no follow-up `--force-reinstall dapr`,
#    leaving the bundled paths missing on disk (the #1 failure mode, after
#    the fact).
#
# Both checks swallow exceptions so unrelated metadata quirks cannot break
# `import dapr`. Set `DAPR_SKIP_LEGACY_CHECK=1` to suppress.

from __future__ import annotations

import importlib.metadata
import os
import sys
import warnings
from pathlib import Path

# Legacy dist name -> directory it shipped under in its pre-1.19 wheel layout.
_LEGACY_DISTS_WITH_BUNDLED_PATHS: dict[str, str] = {
    'dapr-ext-fastapi': 'dapr/ext/fastapi',
    'dapr-ext-grpc': 'dapr/ext/grpc',
    'dapr-ext-langgraph': 'dapr/ext/langgraph',
    'dapr-ext-strands': 'dapr/ext/strands',
    'dapr-ext-workflow': 'dapr/ext/workflow',
    'flask-dapr': 'flask_dapr',
}


def _safe_dist_version(dist: importlib.metadata.Distribution) -> str:
    try:
        return dist.version
    except Exception:
        return '<unknown>'


def _detect_legacy_extension_dists() -> list[str]:
    """Return `name==version` for installed legacy ext distributions.

    Confirms legacy status by checking that the dist actually owns files
    under the bundled path. When RECORD is missing (Debian python3-*, some
    conda channels, sdist --no-binary), conservatively flag the install.
    """
    legacy: list[str] = []
    for dist_name, bundled_path_prefix in _LEGACY_DISTS_WITH_BUNDLED_PATHS.items():
        try:
            dist = importlib.metadata.distribution(dist_name)
        except importlib.metadata.PackageNotFoundError:
            continue
        except Exception:
            continue

        try:
            files = dist.files
        except Exception:
            files = None

        if files is None:
            legacy.append(f'{dist_name}=={_safe_dist_version(dist)}')
            continue

        ships_bundled_path = any(
            str(installed_file).startswith(bundled_path_prefix + '/') for installed_file in files
        )
        if ships_bundled_path:
            legacy.append(f'{dist_name}=={_safe_dist_version(dist)}')
    return legacy


def _detect_missing_bundled_files() -> list[str]:
    """Return bundled extension dirs whose `__init__.py` is missing on disk.

    Catches the post-uninstall, pre-reinstall state. Bails out when dapr is
    loaded from a non-filesystem source (zipapp, frozen bundle) to avoid
    false positives from custom loaders.
    """
    try:
        dapr_root = Path(__file__).resolve().parent
    except OSError:
        return []
    if not dapr_root.is_dir():
        # dapr is loaded from a zipapp / frozen / non-filesystem source;
        # the filesystem layout assumption doesn't apply.
        return []

    site_root = dapr_root.parent
    missing: list[str] = []
    for bundled_path_prefix in _LEGACY_DISTS_WITH_BUNDLED_PATHS.values():
        # `dapr/ext/<name>` lives under our package; `flask_dapr` is a sibling
        # top-level shim at the site-packages root.
        if bundled_path_prefix.startswith('dapr/'):
            init_file = dapr_root / bundled_path_prefix[len('dapr/') :] / '__init__.py'
        else:
            init_file = site_root / bundled_path_prefix / '__init__.py'
        try:
            if not init_file.is_file():
                missing.append(bundled_path_prefix)
        except OSError:
            continue
    return missing


def _emit_legacy_warning(message: str) -> None:
    """Emit a FutureWarning, falling back to stderr under `-W error`.

    Some CI environments set `PYTHONWARNINGS=error`, which would otherwise
    crash `import dapr`. stacklevel=4 lands on the user's `import dapr`:
    warn -> _emit -> _check -> module body.
    """
    try:
        warnings.warn(message, FutureWarning, stacklevel=4)
    except FutureWarning:
        # `-W error::FutureWarning` (or broader) escalated the warning.
        # Fall back to stderr so the user still sees the migration recipe.
        print(f'dapr: FutureWarning: {message}', file=sys.stderr)


def _check_for_legacy_extension_issues() -> None:
    """Run both detectors and emit at most one warning."""
    if os.environ.get('DAPR_SKIP_LEGACY_CHECK', '').strip().lower() in {'1', 'true', 'yes', 'on'}:
        return

    try:
        legacy_installs = _detect_legacy_extension_dists()
    except Exception:
        legacy_installs = []

    if legacy_installs:
        legacy_names = ' '.join(spec.split('==', 1)[0] for spec in legacy_installs)
        _emit_legacy_warning(
            f'Legacy Dapr extension distributions installed alongside core dapr: '
            f'{", ".join(legacy_installs)}. As of dapr 1.19 these ship inside the '
            f'core `dapr` wheel under `dapr.ext.*` and are opt-in via extras. '
            f'To migrate:\n'
            f'  pip uninstall -y {legacy_names}\n'
            f'  pip install --force-reinstall --no-deps dapr\n'
            f'  pip install "dapr[<extras>]"'
        )
        return

    try:
        missing_paths = _detect_missing_bundled_files()
    except Exception:
        missing_paths = []

    if missing_paths:
        _emit_legacy_warning(
            f'Bundled Dapr extension paths missing on disk: {", ".join(missing_paths)}. '
            f'A prior `pip uninstall dapr-ext-*` removed files now owned by core '
            f'`dapr`. Restore with:\n'
            f'  pip install --force-reinstall --no-deps dapr\n'
            f'  pip install "dapr[<extras>]"'
        )


try:
    _check_for_legacy_extension_issues()
except Exception:
    # Never break `import dapr` for unrelated metadata quirks.
    pass
