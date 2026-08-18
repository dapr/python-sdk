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

import os
import platform
import threading
import urllib.parse
import urllib.request

from dapr.version import __version__

# Anonymous usage reporting. PyPI publishes only aggregate download counts, so
# this is the project's only signal about how the SDK is actually used. The SDK
# reports its own version and the host platform once per process. No application
# data is collected. See the "Usage Analytics" section of the README, including
# how to opt out.
ANALYTICS_ENDPOINT = 'https://dapr.gateway.scarf.sh/dapr-event-collection'
ANALYTICS_TIMEOUT_SECONDS = 2

# Honors the cross-ecosystem DO_NOT_TRACK convention, Scarf's own variable, and
# a Dapr-specific opt-out.
OPT_OUT_ENV_VARS = ('DO_NOT_TRACK', 'SCARF_NO_ANALYTICS', 'DAPR_DISABLE_ANALYTICS')
_TRUTHY_VALUES = frozenset({'1', 'true', 'yes', 'on'})

_reported_lock = threading.Lock()
_reported = False


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in _TRUTHY_VALUES


def analytics_disabled() -> bool:
    """Returns True when the user has opted out via any supported variable."""
    return any(_is_truthy(os.environ.get(name, '')) for name in OPT_OUT_ENV_VARS)


def _build_url() -> str:
    params = urllib.parse.urlencode(
        {
            'version': __version__,
            'os': platform.system().lower(),
            'arch': platform.machine().lower(),
            'python_version': platform.python_version(),
        }
    )
    return f'{ANALYTICS_ENDPOINT}?{params}'


def _send_event() -> None:
    """Sends a single event, swallowing every failure.

    Analytics must never affect the application: a blocked egress path or an
    air-gapped cluster is a normal condition, not a fault.
    """
    try:
        request = urllib.request.Request(
            _build_url(),
            headers={'User-Agent': f'dapr-python-sdk/{__version__}'},
        )
        with urllib.request.urlopen(request, timeout=ANALYTICS_TIMEOUT_SECONDS):
            pass
    except Exception:
        pass


def report_analytics() -> None:
    """Reports a usage event once per process, on a background daemon thread.

    Never blocks the caller and never raises.
    """
    global _reported

    try:
        with _reported_lock:
            if _reported:
                return
            _reported = True

        if analytics_disabled():
            return

        thread = threading.Thread(target=_send_event, name='dapr-analytics', daemon=True)
        thread.start()
    except Exception:
        pass
