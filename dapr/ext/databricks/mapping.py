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

import base64
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict

from dapr.ext.databricks._typing import RowLike


def default_row_mapper(row: RowLike) -> Dict[str, Any]:
    """Default ``Row`` -> JSON-compatible ``dict`` mapping for workflow input.

    Delegates field extraction to ``Row.asDict(recursive=True)`` (so nested
    structs/arrays/maps become plain dicts/lists), then normalizes the value
    types that ``asDict`` leaves in a non-JSON-serializable shape.

    Args:
        row: The Spark row for a single record.

    Returns:
        A JSON-serializable dict suitable for use as workflow input.
    """
    return _json_safe(row.asDict(recursive=True))


def _json_safe(value: Any) -> Any:
    """Recursively converts Spark/Python values that ``json.dumps`` cannot handle.

    - ``datetime``/``date`` -> ISO 8601 string.
    - ``Decimal`` -> string, to avoid silently losing precision on monetary
      fields by round-tripping through ``float``.
    - ``bytes``/``bytearray`` -> base64-encoded string.
    - ``dict``/``list``/``tuple`` -> recursed into.
    - Anything else is passed through unchanged.
    """
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return base64.b64encode(bytes(value)).decode('ascii')
    return value
