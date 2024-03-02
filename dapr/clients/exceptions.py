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
import json
from typing import Optional

from google.protobuf.json_format import MessageToDict
from grpc import RpcError  # type: ignore
from grpc_status import rpc_status  # type: ignore
from google.rpc import error_details_pb2  # type: ignore

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


class StatusDetails:
    def __init__(self):
        self.error_info = None
        self.retry_info = None
        self.debug_info = None
        self.quota_failure = None
        self.precondition_failure = None
        self.bad_request = None
        self.request_info = None
        self.resource_info = None
        self.help = None
        self.localized_message = None

    def as_dict(self):
        return {attr: getattr(self, attr) for attr in self.__dict__}


class DaprGrpcError(RpcError):
    def __init__(self, err: RpcError):
        self._status_code = err.code()
        self._err_message = err.details()
        self._details = StatusDetails()

        self._grpc_status = rpc_status.from_call(err)
        self._parse_details()

    def _parse_details(self):
        if self._grpc_status is None:
            return

        for detail in self._grpc_status.details:
            if detail.Is(error_details_pb2.ErrorInfo.DESCRIPTOR):
                self._details.error_info = serialize_status_detail(detail)
            elif detail.Is(error_details_pb2.RetryInfo.DESCRIPTOR):
                self._details.retry_info = serialize_status_detail(detail)
            elif detail.Is(error_details_pb2.DebugInfo.DESCRIPTOR):
                self._details.debug_info = serialize_status_detail(detail)
            elif detail.Is(error_details_pb2.QuotaFailure.DESCRIPTOR):
                self._details.quota_failure = serialize_status_detail(detail)
            elif detail.Is(error_details_pb2.PreconditionFailure.DESCRIPTOR):
                self._details.precondition_failure = serialize_status_detail(detail)
            elif detail.Is(error_details_pb2.BadRequest.DESCRIPTOR):
                self._details.bad_request = serialize_status_detail(detail)
            elif detail.Is(error_details_pb2.RequestInfo.DESCRIPTOR):
                self._details.request_info = serialize_status_detail(detail)
            elif detail.Is(error_details_pb2.ResourceInfo.DESCRIPTOR):
                self._details.resource_info = serialize_status_detail(detail)
            elif detail.Is(error_details_pb2.Help.DESCRIPTOR):
                self._details.help = serialize_status_detail(detail)
            elif detail.Is(error_details_pb2.LocalizedMessage.DESCRIPTOR):
                self._details.localized_message = serialize_status_detail(detail)

    def code(self):
        return self._status_code

    def details(self):
        """
        We're keeping the method name details() so it matches the grpc.RpcError interface.
        @return:
        """
        return self._err_message

    def error_code(self):
        if not self.status_details() or not self.status_details().error_info:
            return ERROR_CODE_UNKNOWN
        return self.status_details().error_info.get('reason', ERROR_CODE_UNKNOWN)

    def status_details(self):
        return self._details

    def get_grpc_status(self):
        return self._grpc_status

    def json(self):
        error_details = {
            'status_code': self.code().name,
            'message': self.details(),
            'error_code': self.error_code(),
            'details': self._details.as_dict(),
        }
        return json.dumps(error_details)


def serialize_status_detail(status_detail):
    if not status_detail:
        return None
    return MessageToDict(status_detail, preserving_proto_field_name=True)
