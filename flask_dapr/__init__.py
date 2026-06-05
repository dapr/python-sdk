# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
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

# TODO: remove in 1.20.
# Deprecation shim for the pre-1.19 `flask_dapr` top-level import path.
# Use `dapr.ext.flask` instead.

import sys
import warnings

# Warn before importing so the migration hint reaches users even when the
# inner import fails (bare `pip install dapr` without the flask extra).
warnings.warn(
    "Importing from 'flask_dapr' is deprecated; "
    "use 'from dapr.ext.flask import DaprActor, DaprApp' instead. "
    "The 'flask_dapr' top-level module will be removed in a future release.",
    FutureWarning,
    stacklevel=2,
)

from dapr.ext.flask import DaprActor, DaprApp, actor, app  # noqa: E402

# Register submodule aliases so `from flask_dapr.actor import DaprActor` and
# `import flask_dapr.app` resolve without on-disk files.
sys.modules['flask_dapr.actor'] = actor
sys.modules['flask_dapr.app'] = app

__all__ = ['DaprActor', 'DaprApp']
