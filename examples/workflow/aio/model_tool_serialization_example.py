"""
Copyright 2025 The Dapr Authors
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

from typing import Any, Dict

from dapr.ext.workflow import ensure_canonical_json

"""
Example of implementing provider-specific model/tool serialization OUTSIDE the core package.

This demonstrates how to build and use your own contracts using the generic helpers from
`dapr.ext.workflow.serializers`.
"""


def to_model_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    req = {
        'schema_version': 'model_req@v1',
        'model_name': payload.get('model_name'),
        'system_instructions': payload.get('system_instructions'),
        'input': payload.get('input'),
        'model_settings': payload.get('model_settings') or {},
        'tools': payload.get('tools') or [],
    }
    return ensure_canonical_json(req, strict=True)


def from_model_response(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        content = obj.get('content')
        tool_calls = obj.get('tool_calls') or []
        out = {'schema_version': 'model_res@v1', 'content': content, 'tool_calls': tool_calls}
        return ensure_canonical_json(out, strict=False)
    return ensure_canonical_json(
        {'schema_version': 'model_res@v1', 'content': str(obj), 'tool_calls': []}, strict=False
    )


def to_tool_request(name: str, args: list | None, kwargs: dict | None) -> Dict[str, Any]:
    req = {
        'schema_version': 'tool_req@v1',
        'tool_name': name,
        'args': args or [],
        'kwargs': kwargs or {},
    }
    return ensure_canonical_json(req, strict=True)


def from_tool_result(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict) and ('result' in obj or 'error' in obj):
        return ensure_canonical_json({'schema_version': 'tool_res@v1', **obj}, strict=False)
    return ensure_canonical_json(
        {'schema_version': 'tool_res@v1', 'result': obj, 'error': None}, strict=False
    )
