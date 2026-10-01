# -*- coding: utf-8 -*-

"""
Copyright 2024 The Dapr Authors
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

import time
import urllib.error
import urllib.request
from warnings import warn

from dapr.clients.http.conf import DAPR_API_TOKEN_HEADER, DAPR_USER_AGENT, USER_AGENT_HEADER
from dapr.clients.http.helpers import get_api_url
from dapr.conf import settings

# Shortest time one health probe may wait for the sidecar. Each probe is otherwise capped
# at what is left of DAPR_HEALTH_TIMEOUT; the floor lets the last probe still get a reply.
_MIN_ATTEMPT_TIMEOUT_SECONDS = 0.5


def _attempt_timeout(deadline: float) -> float:
    """Seconds one health probe may take: what is left until ``deadline`` (a
    ``time.time()`` value), but never less than _MIN_ATTEMPT_TIMEOUT_SECONDS."""
    return max(deadline - time.time(), _MIN_ATTEMPT_TIMEOUT_SECONDS)


class DaprHealth:
    @staticmethod
    def wait_until_ready():
        warn(
            'This method is deprecated. Use DaprHealth.wait_for_sidecar instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        DaprHealth.wait_for_sidecar()

    @staticmethod
    def wait_for_sidecar():
        health_url = f'{get_api_url()}/healthz/outbound'
        headers = {USER_AGENT_HEADER: DAPR_USER_AGENT}
        if settings.DAPR_API_TOKEN is not None:
            headers[DAPR_API_TOKEN_HEADER] = settings.DAPR_API_TOKEN
        timeout = float(settings.DAPR_HEALTH_TIMEOUT)

        start = time.time()
        while True:
            try:
                req = urllib.request.Request(health_url, headers=headers)
                # Without a timeout, a sidecar that accepts the connection but never
                # answers would block here forever, past DAPR_HEALTH_TIMEOUT. urllib
                # applies this per socket operation (connect, each read), not to the
                # whole request, so a probe can overrun the budget somewhat, but it
                # can no longer block forever.
                with urllib.request.urlopen(
                    req,
                    timeout=_attempt_timeout(start + timeout),
                    context=DaprHealth.get_ssl_context(),
                ) as response:
                    if 200 <= response.status < 300:
                        break
            except urllib.error.URLError as e:
                print(f'Health check on {health_url} failed: {e.reason}')
            except Exception as e:
                print(f'Unexpected error during health check: {e}')

            remaining = (start + timeout) - time.time()
            if remaining <= 0:
                raise TimeoutError(f'Dapr health check timed out, after {timeout}.')
            time.sleep(min(1, remaining))

    @staticmethod
    def get_ssl_context():
        # This method is used (overwritten) from tests
        # to return context for self-signed certificates
        return None
