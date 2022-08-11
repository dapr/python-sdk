import grpc
import json

from concurrent import futures
from google.protobuf.any_pb2 import Any as GrpcAny
from google.protobuf import empty_pb2
from dapr.clients.grpc._helpers import to_bytes
from dapr.proto import api_service_v1, common_v1, api_v1
from dapr.proto.runtime.v1.dapr_pb2 import (
    QueryStateItem,
    TryLockRequest,
    TryLockResponse,
    UnlockRequest,
    UnlockResponse,
)


class FakeDaprSidecar(api_service_v1.DaprServicer):
    def __init__(self):
        self._server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        api_service_v1.add_DaprServicer_to_server(self, self._server)
        self.store = {}
        self.shutdown_received = False
        self.locks_to_owner = {}  # (store_name, resource_id) -> lock_owner

    def start(self, port: int = 8080):
        self._server.add_insecure_port(f'[::]:{port}')
        self._server.start()

    def stop(self):
        self._server.stop(None)

    def InvokeService(self, request, context) -> common_v1.InvokeResponse:
        headers = ()
        trailers = ()

        for k, v in context.invocation_metadata():
            headers = headers + (('h' + k, v), )
            trailers = trailers + (('t' + k, v), )

        resp = GrpcAny()
        content_type = ''

        if request.message.method == 'bytes':
            resp.value = request.message.data.value
            content_type = request.message.content_type
        else:
            resp = request.message.data

        context.send_initial_metadata(headers)
        context.set_trailing_metadata(trailers)

        return common_v1.InvokeResponse(data=resp, content_type=content_type)

    def InvokeBinding(self, request, context) -> api_v1.InvokeBindingResponse:
        headers = ()
        trailers = ()

        for k, v in request.metadata.items():
            headers = headers + (('h' + k, v), )
            trailers = trailers + (('t' + k, v), )

        resp_data = b'INVALID'
        metadata = {}

        if request.operation == 'create':
            resp_data = request.data
            metadata = request.metadata

        context.send_initial_metadata(headers)
        context.set_trailing_metadata(trailers)

        return api_v1.InvokeBindingResponse(data=resp_data, metadata=metadata)

    def PublishEvent(self, request, context):
        headers = ()
        trailers = ()
        if request.topic:
            headers = headers + (('htopic', request.topic),)
            trailers = trailers + (('ttopic', request.topic),)
        if request.data:
            headers = headers + (('hdata', request.data), )
            trailers = trailers + (('hdata', request.data), )
        if request.data_content_type:
            headers = headers + (('data_content_type', request.data_content_type), )
            trailers = trailers + (('data_content_type', request.data_content_type), )
        if request.metadata['rawPayload']:
            headers = headers + (('metadata_raw_payload', request.metadata['rawPayload']), )
        if request.metadata['ttlInSeconds']:
            headers = headers + (('metadata_ttl_in_seconds', request.metadata['ttlInSeconds']), )

        context.send_initial_metadata(headers)
        context.set_trailing_metadata(trailers)
        return empty_pb2.Empty()

    def SaveState(self, request, context):
        headers = ()
        trailers = ()
        for state in request.states:
            data = state.value
            if state.metadata["capitalize"]:
                data = to_bytes(data.decode("utf-8").capitalize())
            if state.HasField('etag'):
                self.store[state.key] = (data, state.etag.value)
            else:
                self.store[state.key] = (data, 'ETAG_WAS_NONE')

        context.send_initial_metadata(headers)
        context.set_trailing_metadata(trailers)
        return empty_pb2.Empty()

    def ExecuteStateTransaction(self, request, context):
        headers = ()
        trailers = ()
        for operation in request.operations:
            if operation.operationType == 'delete':
                del self.store[operation.request.key]
            else:
                etag = 'ETAG_WAS_NONE'
                if operation.request.HasField("etag"):
                    etag = operation.request.etag.value
                self.store[operation.request.key] = (operation.request.value, etag)

        context.send_initial_metadata(headers)
        context.set_trailing_metadata(trailers)
        return empty_pb2.Empty()

    def GetState(self, request, context):
        key = request.key
        if key not in self.store:
            return empty_pb2.Empty()
        else:
            data, etag = self.store[key]
            if request.metadata["upper"]:
                data = to_bytes(data.decode("utf-8").upper())
            return api_v1.GetStateResponse(data=data, etag=etag)

    def GetBulkState(self, request, context):
        items = []
        for key in request.keys:
            req = api_v1.GetStateRequest(store_name=request.store_name, key=key)
            res = self.GetState(req, context)
            data = res.data
            etag = res.etag
            if request.metadata["upper"]:
                data = to_bytes(data.decode("utf-8").upper())
            items.append(api_v1.BulkStateItem(key=key, etag=etag, data=data))
        return api_v1.GetBulkStateResponse(items=items)

    def DeleteState(self, request, context):
        headers = ()
        trailers = ()
        key = request.key
        if key in self.store:
            del self.store[key]
        else:
            if request.metadata["must_delete"]:
                raise ValueError("delete failed")

        context.send_initial_metadata(headers)
        context.set_trailing_metadata(trailers)
        return empty_pb2.Empty()

    def GetSecret(self, request, context) -> api_v1.GetSecretResponse:
        headers = ()
        trailers = ()

        key = request.key

        headers = headers + (('keyh', key), )
        trailers = trailers + (('keyt', key), )

        resp = {key: "val"}

        context.send_initial_metadata(headers)
        context.set_trailing_metadata(trailers)

        return api_v1.GetSecretResponse(data=resp)

    def GetBulkSecret(self, request, context) -> api_v1.GetBulkSecretResponse:
        headers = ()
        trailers = ()

        headers = headers + (('keyh', "bulk"), )
        trailers = trailers + (('keyt', "bulk"), )

        resp = {"keya": api_v1.SecretResponse(secrets={"keyb": "val"})}

        context.send_initial_metadata(headers)
        context.set_trailing_metadata(trailers)

        return api_v1.GetBulkSecretResponse(data=resp)

    def GetConfigurationAlpha1(self, request, context):
        items = []
        for key in request.keys:
            items.append({'key': key, 'value': 'value', 'version': '1.5.0', 'metadata': {}})
        return api_v1.GetConfigurationResponse(items=items)

    def SubscribeConfigurationAlpha1(self, request, context):
        items = []
        for key in request.keys:
            item = {'key': key, 'value': 'value', 'version': '1.5.0', 'metadata': {}}
            items.append(item)
        response = {
            items: items
        }
        responses = []
        responses.append(response)
        return api_v1.SubscribeConfigurationResponse(responses=responses)

    def UnsubscribeConfigurationAlpha1(self, request, context):
        return api_v1.UnsubscribeConfigurationResponse(ok=True)

    def QueryStateAlpha1(self, request, context):
        items = [QueryStateItem(
            key=str(key), data=bytes('value of ' + str(key), 'UTF-8')) for key in range(1, 11)]
        query = json.loads(request.query)

        tokenIndex = 1
        if 'page' in query:
            if 'token' in query['page']:
                # For testing purposes, we return a token that is the same as the key
                tokenIndex = int(query['page']['token'])
                items = items[tokenIndex - 1:]
            if 'limit' in query['page']:
                limit = int(query['page']['limit'])
                if len(items) > limit:
                    items = items[:limit]
                tokenIndex = tokenIndex + len(items)

        return api_v1.QueryStateResponse(results=items, token=str(tokenIndex))

    def TryLockAlpha1(self, request: TryLockRequest, context):
        lock_id = (request.store_name, request.resource_id)

        if lock_id not in self.locks_to_owner:
            self.locks_to_owner[lock_id] = request.lock_owner
            return TryLockResponse(success=True)
        else:
            # Lock already acquired
            return TryLockResponse(success=False)

    def UnlockAlpha1(self, request: UnlockRequest, context):
        lock_id = (request.store_name, request.resource_id)

        if lock_id not in self.locks_to_owner:
            return UnlockResponse(status=UnlockResponse.Status.LOCK_DOES_NOT_EXIST)
        elif self.locks_to_owner[lock_id] == request.lock_owner:
            del self.locks_to_owner[lock_id]
            return UnlockResponse(status=UnlockResponse.Status.SUCCESS)
        else:
            return UnlockResponse(status=UnlockResponse.Status.LOCK_BELONGS_TO_OTHERS)

    def Shutdown(self, request, context):
        self.shutdown_received = True
        return empty_pb2.Empty()
