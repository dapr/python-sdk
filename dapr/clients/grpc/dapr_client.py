# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import grpc

from dapr.conf import settings

from dapr.clients.base import DaprClientBase, GrpcAny
from dapr.proto import api_v1, api_service_v1, common_v1
from typing import Union


class DaprClient:
    def __init__(self):
        self._channel = grpc.insecure_channel(f"127.0.0.1:{settings.DAPR_GRPC_PORT}")
        self._stub = api_service_v1.DaprStub(self._channel)

    def invoke_service(
            self,
            target_id: str,
            method: str,
            data: Union[bytes, Any],
            content_type: Optional[str] = DEFAULT_JSON_CONTENT_TYPE,
            metadata: Optional[Dict[str, str]] = None,
            http_verb: Optional[str] = None,
            http_querystring: Optional[Dict[str, str]] = None) -> Tuple[Union[bytes, GrpcAny], Dict[str, str]]:

        msg = data
        if isinstance(data, bytes):
            msg = Any(value=data)

        req = api_v1.InvokeServiceRequest(
            id=target_id,
            message=common_v1.InvokeRequest(
                method=method,
                data=msg,
                content_type=content_type)
        )

        response, call = self._stub.InvokeService.with_call(req)
        
        headers = {}
        for key, value in call.initial_metadata():
            headers[key] = value

        return (resp_data, headers)