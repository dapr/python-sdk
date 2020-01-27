# -*- coding: utf-8 -*-
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dapr.conf import settings
from dapr.clients.base import DaprActorClientBase

import io
import requests
import json

_DEFAULT_CHUNK_SIZE=1024
_DEFAULT_ENCODING='utf-8'
_DEFAULT_CONTENT_TYPE='application/octet-stream'
_DEFAULT_JSON_CONTENT_TYPE="application/json; charset={}".format(_DEFAULT_ENCODING)

class DaprActorHttpClient(DaprActorClientBase):

    def __init__(
        self,
        timeout=10):

        self._session = requests.Session()
        self._timeout = (1, timeout)

    def _get_base_url(self, actor_type, actor_id) -> str:
        return 'http://localhost:{}/{}/actors/{}/{}'.format(
            settings.DAPR_HTTP_PORT,
            settings.DAPR_API_VERSION,
            actor_type,
            actor_id)

    def _send_raw(self, method: str, url: str, data: bytes, headers=None) -> bytes:
        if headers is None:
            headers = {}
        if getattr(headers, 'content-type') is None:
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

    def invoke_method(
        self,
        actor_type: str,
        actor_id: str,
        method: str,
        data: bytes,
        headers = None) -> bytes:

        url = '{}/method/{}'.format(
            self._get_base_url(actor_type, actor_id),
            method)

        return self._send_raw(method='POST', url=url, data=data)
