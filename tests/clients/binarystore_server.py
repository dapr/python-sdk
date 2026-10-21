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

import threading

import grpc

from dapr.proto import common_v1
from dapr.proto.runtime.v1 import binarystore_pb2 as binary_v1
from tests.clients.fake_dapr_server import FakeDaprSidecar


class BinaryStoreSidecar(FakeDaprSidecar):
    """Existing localhost sidecar extended with controllable binary-store RPCs."""

    def __init__(self):
        super().__init__()
        self.files = {}
        self.uploads = []
        self.calls = []
        self.upload_error = None
        self.upload_error_after_body = None
        self.download_error = None
        self.download_messages = None
        self.wait_for_upload = False
        self.upload_received = threading.Event()
        self.upload_release = threading.Event()
        self.hold_upload_body = False
        self.upload_body_started = threading.Event()
        self.upload_body_release = threading.Event()
        self.hold_download = False
        self.download_started = threading.Event()
        self.download_cancelled = threading.Event()
        self.token = None

    def _record(self, method, context):
        metadata = list(context.invocation_metadata())
        self.calls.append((method, metadata, context.time_remaining()))
        if self.token is not None and ('dapr-api-token', self.token) not in metadata:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, 'missing token')
        context.send_initial_metadata((('binary-header', 'value'),))

    def SetBinaryFileAlpha1(self, requests, context):
        self._record('set', context)
        messages = []
        self.uploads.append(messages)
        first = next(requests)
        messages.append(first)
        if self.upload_error is not None:
            context.abort(self.upload_error, 'upload rejected')
        initial = first.initial_request
        key = (initial.component_name, initial.file_name)
        if key in self.files and not initial.overwrite:
            context.abort(grpc.StatusCode.ALREADY_EXISTS, 'file exists')
        self.upload_body_started.set()
        if self.hold_upload_body:
            while context.is_active() and not self.upload_body_release.wait(0.01):
                pass
        chunks = []
        for request in requests:
            messages.append(request)
            chunks.append(request.payload.data)
        if self.upload_error_after_body is not None:
            context.abort(self.upload_error_after_body, 'upload interrupted')
        self.upload_received.set()
        if self.wait_for_upload:
            while context.is_active() and not self.upload_release.wait(0.01):
                pass
        self.files[key] = b''.join(chunks)
        return binary_v1.SetBinaryFileResponseAlpha1()

    def GetBinaryFileAlpha1(self, request, context):
        self._record('get', context)
        context.add_callback(self.download_cancelled.set)
        key = (request.component_name, request.file_name)
        if self.download_messages is not None:
            yield from self.download_messages
        elif key in self.files:
            data = self.files[key]
            for seq, start in enumerate(range(0, len(data), 32768)):
                yield binary_v1.GetBinaryFileResponseAlpha1(
                    payload=common_v1.StreamPayload(data=data[start : start + 32768], seq=seq)
                )
        else:
            context.abort(grpc.StatusCode.NOT_FOUND, 'missing file')
        self.download_started.set()
        if self.download_error is not None:
            context.abort(self.download_error, 'download interrupted')
        if self.hold_download:
            self.download_cancelled.wait(10)

    def DeleteBinaryFileAlpha1(self, request, context):
        self._record('delete', context)
        key = (request.component_name, request.file_name)
        if key not in self.files:
            context.abort(grpc.StatusCode.NOT_FOUND, 'missing file')
        del self.files[key]
        return binary_v1.DeleteBinaryFileResponseAlpha1()

    def EncryptAlpha1(self, requests, context):
        self._record('encrypt', context)
        yield from super().EncryptAlpha1(requests, context)
