# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""
import io
import requests

from dapr.conf import settings
from dapr.clients.base import DaprActorClientBase

_DEFAULT_CHUNK_SIZE=1024
_DEFAULT_ENCODING='utf-8'
_DEFAULT_CONTENT_TYPE='application/octet-stream'
_DEFAULT_JSON_CONTENT_TYPE=f'application/json; charset={_DEFAULT_ENCODING}'

class DaprActorHttpClient(DaprActorClientBase):
    """A Dapr Actor http client implementing :class:`DaprActorClientBase`"""

    def __init__(self, timeout=10):
        self._session = requests.Session()
        self._timeout = (1, timeout)

    def invoke_method(self, actor_type: str, actor_id: str,
            method: str, data: bytes) -> bytes:
        """Invoke method defined in :class:`Actor` remotely.

        :param actor_type: str to represent Actor type.
        :param actor_id: str to represent id of Actor type.
        :param method: str to invoke method defined in :class:`Actor`.
        :param data: bytes, passed to method defined in Actor.
        :rtype: bytes
        """
        url = f'{self._get_base_url(actor_type, actor_id)}/method/{method}'
        return self._send_bytes(method='POST', url=url, data=data)

    def _get_base_url(self, actor_type: str, actor_id: str) -> str:
        return 'http://localhost:{}/{}/actors/{}/{}'.format(
            settings.DAPR_HTTP_PORT,
            settings.DAPR_API_VERSION,
            actor_type,
            actor_id)

    def _send_bytes(self, method: str, url: str, data: bytes, headers: dict={}) -> bytes:
        if not getattr(headers, 'content-type'):
            headers['content-type'] = _DEFAULT_CONTENT_TYPE

        req = requests.Request(
            method=method,
            url=url,
            data=data,
            headers=headers)

        prepped = req.prepare()
        r = self._session.send(prepped, stream=True, timeout=self._timeout)
        buf = io.BytesIO()
        for chunk in r.iter_content(chunk_size=_DEFAULT_CHUNK_SIZE):
            buf.write(chunk)

        if r.status_code >= 200 and r.status_code < 300:
            return buf.getvalue()
        
        r.raise_for_status()
