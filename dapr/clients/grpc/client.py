# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import grpc  # type: ignore

from typing import Optional

from dapr.conf import settings
from dapr.proto import api_v1, api_service_v1, common_v1

from dapr.clients.grpc._helpers import MetadataTuple
from dapr.clients.grpc.client_request import InvokeServiceRequestData
from dapr.clients.grpc.client_response import InvokeServiceResponse


class DaprClient:
    def __init__(self, address: Optional[str] = None):
        if not address:
            address = f"127.0.0.1:{settings.DAPR_GRPC_PORT}"
        self._channel = grpc.insecure_channel(address)
        self._stub = api_service_v1.DaprStub(self._channel)

    def __del__(self):
        self._channel.close()

    def _get_http_extension(
            self, http_verb: str,
            http_querystring: Optional[MetadataTuple] = ()
    ) -> common_v1.HTTPExtension:  # type: ignore
        verb = common_v1.HTTPExtension.Verb.Value(http_verb)  # type: ignore
        http_ext = common_v1.HTTPExtension(verb=verb)
        for key, val in http_querystring:  # type: ignore
            http_ext.querystring[key] = val
        return http_ext

    def invoke_service(
            self,
            target_id: str,
            method: str,
            data: InvokeServiceRequestData,
            metadata: Optional[MetadataTuple] = None,
            http_verb: Optional[str] = None,
            http_querystring: Optional[MetadataTuple] = None) -> InvokeServiceResponse:
        """Invoke target_id service to call method.

        :param str target_id: str to represent target App ID.
        :param str method: str to represent method name defined in target_id
        :param InvokeServiceRequestData data: bytes or Message for data which will send to target_id
        :param MetadataTuple metadata: dict to pass custom metadata to target app
        :param str http_verb: http method verb to call HTTP callee application
        :param MetadataTuple http_querystring: dict to represent querystring for HTTP callee app

        :returns: the response from callee
        :rtype: InvokeServiceResponse
        """
        http_ext = None
        if http_verb:
            http_ext = self._get_http_extension(http_verb, http_querystring)

        req = api_v1.InvokeServiceRequest(
            id=target_id,
            message=common_v1.InvokeRequest(
                method=method,
                data=data.proto,
                content_type=data.content_type,
                http_extension=http_ext)
        )

        response, call = self._stub.InvokeService.with_call(req, metadata=metadata)

        return InvokeServiceResponse(
            response.data, response.content_type,
            call.initial_metadata(), call.trailing_metadata())
