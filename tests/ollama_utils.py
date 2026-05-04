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
