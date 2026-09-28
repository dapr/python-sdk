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

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import httpx

from dapr.credentials.base import CredentialProvider, WorkloadCredential
from dapr.credentials.sources import AttestationSource

SUBJECT_TOKEN_TYPE_JWT = 'urn:ietf:params:oauth:token-type:jwt'
REQUESTED_TOKEN_TYPE_ACCESS_TOKEN = 'urn:ietf:params:oauth:token-type:access_token'
GRANT_TYPE_TOKEN_EXCHANGE = 'urn:ietf:params:oauth:grant-type:token-exchange'

DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_ERROR_BODY_CHARS = 500


class RFC8693TokenExchangeProvider(CredentialProvider):
    """Exchanges an attestation token for a bearer credential via RFC 8693 OAuth 2.0 Token
    Exchange.

    ``attestation`` supplies the subject token, e.g. a Kubernetes projected service account
    token; ``token_url`` is the identity provider's token endpoint. The credential expires
    per the response's ``expires_in``, and is treated as long-lived if that is omitted.
    """

    def __init__(
        self,
        token_url: str,
        attestation: AttestationSource,
        *,
        audience: Optional[str] = None,
        scope: Optional[str] = None,
        subject_token_type: str = SUBJECT_TOKEN_TYPE_JWT,
        requested_token_type: str = REQUESTED_TOKEN_TYPE_ACCESS_TOKEN,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: Optional[httpx.BaseTransport] = None,
        async_transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        """
        Args:
            transport: httpx transport for :meth:`fetch`, e.g. ``httpx.MockTransport``.
            async_transport: httpx transport for :meth:`fetch_async`.
        """
        self._token_url = token_url
        self._attestation = attestation
        self._audience = audience
        self._scope = scope
        self._subject_token_type = subject_token_type
        self._requested_token_type = requested_token_type
        self._timeout_seconds = timeout_seconds
        self._transport = transport
        self._async_transport = async_transport

    def fetch(self) -> WorkloadCredential:
        with httpx.Client(timeout=self._timeout_seconds, transport=self._transport) as client:
            response = client.post(self._token_url, data=self._build_form())
        return self._parse_response(response)

    async def fetch_async(self) -> WorkloadCredential:
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds, transport=self._async_transport
        ) as client:
            response = await client.post(self._token_url, data=self._build_form())
        return self._parse_response(response)

    def _build_form(self) -> Dict[str, str]:
        form = {
            'grant_type': GRANT_TYPE_TOKEN_EXCHANGE,
            'subject_token': self._attestation.get(),
            'subject_token_type': self._subject_token_type,
            'requested_token_type': self._requested_token_type,
        }
        if self._audience:
            form['audience'] = self._audience
        if self._scope:
            form['scope'] = self._scope
        return form

    def _parse_response(self, response: httpx.Response) -> WorkloadCredential:
        if response.is_error:
            raise httpx.HTTPStatusError(
                f"token exchange with '{self._token_url}' failed with "
                f'{response.status_code}: {response.text[:MAX_ERROR_BODY_CHARS]}',
                request=response.request,
                response=response,
            )
        payload = response.json()

        access_token = payload.get('access_token')
        if not access_token:
            raise ValueError(
                f"token exchange response from '{self._token_url}' is missing 'access_token'"
            )

        expires_at = self._parse_expiry(payload.get('expires_in'))
        return WorkloadCredential(token=access_token, expires_at=expires_at)

    def _parse_expiry(self, expires_in: object) -> Optional[datetime]:
        if expires_in is None:
            return None
        if isinstance(expires_in, bool) or not isinstance(expires_in, (int, float)):
            raise ValueError(
                f"token exchange response from '{self._token_url}' has a non-numeric "
                f"'expires_in': {expires_in!r}"
            )
        return datetime.now(timezone.utc) + timedelta(seconds=expires_in)
