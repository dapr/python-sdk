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

# The core clients import this package, so it re-exports only stdlib-backed names. The token
# exchange provider needs dapr[workload-identity]; import it from dapr.credentials.oauth2.
from dapr.credentials.base import CredentialProvider, WorkloadCredential
from dapr.credentials.manager import AsyncCredentialManager, CredentialManager
from dapr.credentials.sources import (
    AttestationSource,
    CallableAttestationSource,
    FileAttestationSource,
    kubernetes_service_account_source,
)

__all__ = [
    'CredentialProvider',
    'WorkloadCredential',
    'CredentialManager',
    'AsyncCredentialManager',
    'AttestationSource',
    'CallableAttestationSource',
    'FileAttestationSource',
    'kubernetes_service_account_source',
]
