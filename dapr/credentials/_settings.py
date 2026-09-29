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

import logging
from typing import Optional

from dapr.conf import settings
from dapr.credentials.base import CredentialProvider
from dapr.credentials.sources import FileAttestationSource

logger = logging.getLogger(__name__)


def resolve_default_credential_provider() -> Optional[CredentialProvider]:
    """Builds the RFC 8693 token exchange provider configured through settings, if any.

    ``DAPR_WORKLOAD_IDENTITY_TOKEN_URL`` and ``DAPR_WORKLOAD_IDENTITY_TOKEN_FILE_PATH``
    enable it, optionally with ``DAPR_WORKLOAD_IDENTITY_AUDIENCE`` and ``_SCOPE``. It takes
    precedence over ``DAPR_API_TOKEN``, with a warning.

    Returns:
        The provider, or ``None`` if it isn't configured.

    Raises:
        ValueError: If only one of the two required settings is set.
    """
    token_url = settings.DAPR_WORKLOAD_IDENTITY_TOKEN_URL
    token_file_path = settings.DAPR_WORKLOAD_IDENTITY_TOKEN_FILE_PATH
    if not token_url and not token_file_path:
        return None
    if not (token_url and token_file_path):
        raise ValueError(
            'DAPR_WORKLOAD_IDENTITY_TOKEN_URL and DAPR_WORKLOAD_IDENTITY_TOKEN_FILE_PATH must '
            'be set together'
        )

    if settings.DAPR_API_TOKEN:
        logger.warning(
            'both DAPR_API_TOKEN and a workload identity credential are configured; the '
            'workload identity credential takes precedence and DAPR_API_TOKEN is ignored'
        )

    # Imported lazily: it requires dapr[workload-identity], which the core clients don't.
    from dapr.credentials.oauth2 import RFC8693TokenExchangeProvider

    return RFC8693TokenExchangeProvider(
        token_url=token_url,
        attestation=FileAttestationSource(token_file_path),
        audience=settings.DAPR_WORKLOAD_IDENTITY_AUDIENCE,
        scope=settings.DAPR_WORKLOAD_IDENTITY_SCOPE,
    )
