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

from __future__ import annotations

import httpx

OLLAMA_URL = 'http://localhost:11434'
DEFAULT_MODEL = 'llama3.2:latest'


def ollama_ready() -> bool:
    try:
        return httpx.get(f'{OLLAMA_URL}/api/tags', timeout=2).is_success
    except httpx.RequestError:
        return False


def model_available(model: str = DEFAULT_MODEL) -> bool:
    try:
        resp = httpx.get(f'{OLLAMA_URL}/api/tags', timeout=5)
        resp.raise_for_status()
    except httpx.RequestError:
        return False
    return any(m['name'] == model for m in resp.json().get('models', []))
