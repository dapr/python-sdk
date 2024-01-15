# -*- coding: utf-8 -*-

"""
Copyright 2023 The Dapr Authors
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

from typing import Optional
from grpc import RpcError
from grpc_status import rpc_status  # type: ignore
from google.rpc import error_details_pb2

ERROR_CODE_UNKNOWN = 'UNKNOWN'
ERROR_CODE_DOES_NOT_EXIST = 'ERR_DOES_NOT_EXIST'


class DaprInternalError(Exception):
    """DaprInternalError encapsulates all Dapr exceptions"""

    def __init__(
        self,
        message: Optional[str],
        error_code: Optional[str] = ERROR_CODE_UNKNOWN,
        raw_response_bytes: Optional[bytes] = None,
    ):
        self._message = message
        self._error_code = error_code
        self._raw_response_bytes = raw_response_bytes

    def as_dict(self):
        return {
            'message': self._message,
            'errorCode': self._error_code,
            'raw_response_bytes': self._raw_response_bytes,
        }


class DaprGrpcError(RpcError):
    def __init__(self, err: RpcError):
        self.status_code = err.code()
        self.error_info = None  # Initialize attributes
        self.retry_info = None
        self.debug_info = None
        self.quota_failure = None
        self.precondition_failure = None
        self.bad_request = None
        self.request_info = None
        self.resource_info = None
        self.help = None
        self.localized_message = None

        self.status = rpc_status.from_call(err)
        self._parse_details()

    def _parse_details(self):
        for detail in self.status_details():
            if detail.Is(error_details_pb2.ErrorInfo.DESCRIPTOR):
                self.error_info = error_details_pb2.ErrorInfo()
                detail.Unpack(self.error_info)
            elif detail.Is(error_details_pb2.RetryInfo.DESCRIPTOR):
                self.retry_info = error_details_pb2.RetryInfo()
                detail.Unpack(self.retry_info)
            elif detail.Is(error_details_pb2.DebugInfo.DESCRIPTOR):
                self.debug_info = error_details_pb2.DebugInfo()
                detail.Unpack(self.debug_info)
            elif detail.Is(error_details_pb2.QuotaFailure.DESCRIPTOR):
                self.quota_failure = error_details_pb2.QuotaFailure()
                detail.Unpack(self.quota_failure)
            elif detail.Is(error_details_pb2.PreconditionFailure.DESCRIPTOR):
                self.precondition_failure = error_details_pb2.PreconditionFailure()
                detail.Unpack(self.precondition_failure)
            elif detail.Is(error_details_pb2.BadRequest.DESCRIPTOR):
                self.bad_request = error_details_pb2.BadRequest()
                detail.Unpack(self.bad_request)
            elif detail.Is(error_details_pb2.RequestInfo.DESCRIPTOR):
                self.request_info = error_details_pb2.RequestInfo()
                detail.Unpack(self.request_info)
            elif detail.Is(error_details_pb2.ResourceInfo.DESCRIPTOR):
                self.resource_info = error_details_pb2.ResourceInfo()
                detail.Unpack(self.resource_info)
            elif detail.Is(error_details_pb2.Help.DESCRIPTOR):
                self.help = error_details_pb2.Help()
                detail.Unpack(self.help)
            elif detail.Is(error_details_pb2.LocalizedMessage.DESCRIPTOR):
                self.localized_message = error_details_pb2.LocalizedMessage()
                detail.Unpack(self.localized_message)

    def code(self):
        return self.status_code

    def message(self):
        if not self.status:
            return ""
        return self.status.message

    def error_code(self):
        if not self.error_info:
            return ERROR_CODE_UNKNOWN
        return self.error_info.reason

    def status_details(self):
        if not self.status or not self.status.details:
            return []
        return self.status.details
