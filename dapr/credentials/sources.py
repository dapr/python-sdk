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

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional, Union

DEFAULT_KUBERNETES_TOKEN_PATH = Path('/var/run/secrets/dapr.io/serviceaccount/token')


class AttestationSource(ABC):
    """Supplies the token a provider presents to an identity provider to prove the workload's
    identity, e.g. a Kubernetes projected service account token or a cloud workload identity
    token.
    """

    @abstractmethod
    def get(self) -> str:
        """Returns the current attestation material."""


class CallableAttestationSource(AttestationSource):
    """An attestation token produced by an arbitrary callable, invoked on every fetch."""

    def __init__(self, get_token: Callable[[], str]) -> None:
        self._get_token = get_token

    def get(self) -> str:
        return self._get_token()


class FileAttestationSource(AttestationSource):
    """An attestation token re-read from disk on every call, so rotated files (e.g. a
    kubelet-refreshed projected token) are picked up.
    """

    def __init__(self, path: Union[str, Path]) -> None:
        self._path = Path(path)

    def get(self) -> str:
        return self._path.read_text(encoding='utf-8').strip()


def kubernetes_service_account_source(
    path: Optional[Union[str, Path]] = None,
) -> FileAttestationSource:
    """Builds a source for a Kubernetes projected service account token.

    Args:
        path: Token file path. Defaults to :data:`DEFAULT_KUBERNETES_TOKEN_PATH`, where the pod
            spec must mount a ``projected`` volume with a ``serviceAccountToken`` source.
    """
    return FileAttestationSource(path or DEFAULT_KUBERNETES_TOKEN_PATH)
