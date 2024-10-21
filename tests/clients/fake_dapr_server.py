import grpc
import json

from concurrent import futures
from google.protobuf.any_pb2 import Any as GrpcAny
from google.protobuf import empty_pb2, struct_pb2
from google.rpc import status_pb2, code_pb2
from grpc_status import rpc_status

from dapr.clients.grpc._helpers import to_bytes
from dapr.proto import api_service_v1, common_v1, api_v1, appcallback_v1
from dapr.proto.common.v1.common_pb2 import ConfigurationItem
from dapr.clients.grpc._response import WorkflowRuntimeStatus
from dapr.proto.runtime.v1.dapr_pb2 import (
    ActiveActorsCount,
    GetMetadataResponse,
    QueryStateItem,
    RegisteredComponents,
    SetMetadataRequest,
    TryLockRequest,
    TryLockResponse,
    UnlockRequest,
    UnlockResponse,
    StartWorkflowRequest,
    StartWorkflowResponse,
    GetWorkflowRequest,
    GetWorkflowResponse,
    PauseWorkflowRequest,
    ResumeWorkflowRequest,
    TerminateWorkflowRequest,
    PurgeWorkflowRequest,
    RaiseEventWorkflowRequest,
    EncryptRequest,
    EncryptResponse,
    DecryptRequest,
    DecryptResponse,
)
from typing import Dict

from tests.clients.certs import GrpcCerts
from tests.clients.fake_http_server import FakeHttpServer


class FakeDaprSidecar(api_service_v1.DaprServicer):
    def __init__(self, grpc_port: int = 50001, http_port: int = 8080):
        self.grpc_port = grpc_port
        self.http_port = http_port
        self._grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        self._http_server = FakeHttpServer(self.http_port)  # Needed for the healthcheck endpoint
        api_service_v1.add_DaprServicer_to_server(self, self._grpc_server)
        self.store = {}
        self.shutdown_received = False
        self.locks_to_owner = {}  # (store_name, resource_id) -> lock_owner
        self.workflow_status = {}
        self.workflow_options: Dict[str, str] = {}
        self.metadata: Dict[str, str] = {}
        self._next_exception = None

    def start(self):
        self._grpc_server.add_insecure_port(f'[::]:{self.grpc_port}')
        self._grpc_server.start()
        self._http_server.start()

    def start_secure(self):
        GrpcCerts.create_certificates()

        private_key_file = open(GrpcCerts.get_pk_path(), 'rb')
        private_key_content = private_key_file.read()
        private_key_file.close()

        certificate_chain_file = open(GrpcCerts.get_cert_path(), 'rb')
        certificate_chain_content = certificate_chain_file.read()
        certificate_chain_file.close()

        credentials = grpc.ssl_server_credentials(
            [(private_key_content, certificate_chain_content)]
        )

        self._grpc_server.add_secure_port(f'[::]:{self.grpc_port}', credentials)
        self._grpc_server.start()

        self._http_server.start_secure()

    def stop(self):
        self._http_server.shutdown_server()
        self._grpc_server.stop(None)

    def stop_secure(self):
        self._http_server.shutdown_server()
        self._grpc_server.stop(None)
        GrpcCerts.delete_certificates()

    def raise_exception_on_next_call(self, exception):
        """
        Raise an exception on the next call to the server.
        Useful for testing error handling.
        @param exception:
        """
        self._next_exception = exception

    def check_for_exception(self, context):
        """
        Check if an exception was raised on the last call to the server.
        Useful for testing error handling.
        @return: The raised exception, or None if no exception was raised.
        """

        exception = self._next_exception
        self._next_exception = None

        if exception is None:
            return None

        context.abort_with_status(rpc_status.to_status(exception))

    def InvokeService(self, request, context) -> common_v1.InvokeResponse:
        headers = ()
        trailers = ()

        for k, v in context.invocation_metadata():
            headers = headers + (('h' + k, v),)
            trailers = trailers + (('t' + k, v),)

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
            headers = headers + (('h' + k, v),)
            trailers = trailers + (('t' + k, v),)

        resp_data = b'INVALID'
        metadata = {}

        if request.operation == 'create':
            resp_data = request.data
            metadata = request.metadata

        context.send_initial_metadata(headers)
        context.set_trailing_metadata(trailers)

        return api_v1.InvokeBindingResponse(data=resp_data, metadata=metadata)

    def PublishEvent(self, request, context):
        self.check_for_exception(context)

        headers = ()
        trailers = ()
        if request.topic:
            headers = headers + (('htopic', request.topic),)
            trailers = trailers + (('ttopic', request.topic),)
        if request.data:
            headers = headers + (('hdata', request.data),)
            trailers = trailers + (('hdata', request.data),)
        if request.data_content_type:
            headers = headers + (('data_content_type', request.data_content_type),)
            trailers = trailers + (('data_content_type', request.data_content_type),)
        if request.metadata['rawPayload']:
            headers = headers + (('metadata_raw_payload', request.metadata['rawPayload']),)
        if request.metadata['ttlInSeconds']:
            headers = headers + (('metadata_ttl_in_seconds', request.metadata['ttlInSeconds']),)

        context.send_initial_metadata(headers)
        context.set_trailing_metadata(trailers)
        return empty_pb2.Empty()

    def SubscribeTopicEventsAlpha1(self, request_iterator, context):
        for request in request_iterator:
            if request.HasField('initial_request'):
                yield api_v1.SubscribeTopicEventsResponseAlpha1(
                    initial_response=api_v1.SubscribeTopicEventsResponseInitialAlpha1()
                )
                break

        extensions = struct_pb2.Struct()
        extensions.update({'field1': 'value1', 'field2': 42, 'field3': True})

        msg1 = appcallback_v1.TopicEventRequest(
            id='111',
            topic='TOPIC_A',
            data=b'hello2',
            source='app1',
            data_content_type='text/plain',
            type='com.example.type2',
            pubsub_name='pubsub',
            spec_version='1.0',
            extensions=extensions,
        )
        yield api_v1.SubscribeTopicEventsResponseAlpha1(event_message=msg1)

        for request in request_iterator:
            if request.HasField('event_processed'):
                break

        msg2 = appcallback_v1.TopicEventRequest(
            id='222',
            topic='TOPIC_A',
            data=b'{"a": 1}',
            source='app1',
            data_content_type='application/json',
            type='com.example.type2',
            pubsub_name='pubsub',
            spec_version='1.0',
            extensions=extensions,
        )
        yield api_v1.SubscribeTopicEventsResponseAlpha1(event_message=msg2)

        for request in request_iterator:
            if request.HasField('event_processed'):
                break

        # On the third message simulate a disconnection
        context.abort_with_status(
            rpc_status.to_status(
                status_pb2.Status(code=code_pb2.UNAVAILABLE, message='Simulated disconnection')
            )
        )

    def SaveState(self, request, context):
        self.check_for_exception(context)

        headers = ()
        trailers = ()
        for state in request.states:
            data = state.value
            if state.metadata['capitalize']:
                data = to_bytes(data.decode('utf-8').capitalize())
            if state.HasField('etag'):
                self.store[state.key] = (data, state.etag.value)
            else:
                self.store[state.key] = (data, 'ETAG_WAS_NONE')

        context.send_initial_metadata(headers)
        context.set_trailing_metadata(trailers)
        return empty_pb2.Empty()

    def ExecuteStateTransaction(self, request, context):
        self.check_for_exception(context)

        headers = ()
        trailers = ()
        for operation in request.operations:
            if operation.operationType == 'delete':
                del self.store[operation.request.key]
            else:
                etag = 'ETAG_WAS_NONE'
                if operation.request.HasField('etag'):
                    etag = operation.request.etag.value
                self.store[operation.request.key] = (operation.request.value, etag)

        context.send_initial_metadata(headers)
        context.set_trailing_metadata(trailers)
        return empty_pb2.Empty()

    def GetState(self, request, context):
        self.check_for_exception(context)

        key = request.key
        if key not in self.store:
            return empty_pb2.Empty()
        else:
            data, etag = self.store[key]
            if request.metadata['upper']:
                data = to_bytes(data.decode('utf-8').upper())
            return api_v1.GetStateResponse(data=data, etag=etag)

    def GetBulkState(self, request, context):
        self.check_for_exception(context)

        items = []
        for key in request.keys:
            req = api_v1.GetStateRequest(store_name=request.store_name, key=key)
            res = self.GetState(req, context)
            data = res.data
            etag = res.etag
            if request.metadata['upper']:
                data = to_bytes(data.decode('utf-8').upper())
            items.append(api_v1.BulkStateItem(key=key, etag=etag, data=data))
        return api_v1.GetBulkStateResponse(items=items)

    def DeleteState(self, request, context):
        self.check_for_exception(context)

        headers = ()
        trailers = ()
        key = request.key
        if key in self.store:
            del self.store[key]
        else:
            if request.metadata['must_delete']:
                raise ValueError('delete failed')

        context.send_initial_metadata(headers)
        context.set_trailing_metadata(trailers)
        return empty_pb2.Empty()

    def GetSecret(self, request, context) -> api_v1.GetSecretResponse:
        headers = ()
        trailers = ()

        key = request.key

        headers = headers + (('keyh', key),)
        trailers = trailers + (('keyt', key),)

        resp = {key: 'val'}

        context.send_initial_metadata(headers)
        context.set_trailing_metadata(trailers)

        return api_v1.GetSecretResponse(data=resp)

    def GetBulkSecret(self, request, context) -> api_v1.GetBulkSecretResponse:
        headers = ()
        trailers = ()

        headers = headers + (('keyh', 'bulk'),)
        trailers = trailers + (('keyt', 'bulk'),)

        resp = {'keya': api_v1.SecretResponse(secrets={'keyb': 'val'})}

        context.send_initial_metadata(headers)
        context.set_trailing_metadata(trailers)

        return api_v1.GetBulkSecretResponse(data=resp)

    def GetConfiguration(self, request, context):
        items = dict()
        for key in request.keys:
            items[str(key)] = ConfigurationItem(value='value', version='1.5.0')
        return api_v1.GetConfigurationResponse(items=items)

    def SubscribeConfiguration(self, request, context):
        items = []
        for key in request.keys:
            item = {'key': key, 'value': 'value', 'version': '1.5.0', 'metadata': {}}
            items.append(item)
        response = {items: items}
        responses = []
        responses.append(response)
        return api_v1.SubscribeConfigurationResponse(responses=responses)

    def UnsubscribeConfiguration(self, request, context):
        return api_v1.UnsubscribeConfigurationResponse(ok=True)

    def QueryStateAlpha1(self, request, context):
        self.check_for_exception(context)

        items = [
            QueryStateItem(key=str(key), data=bytes('value of ' + str(key), 'UTF-8'))
            for key in range(1, 11)
        ]
        query = json.loads(request.query)

        tokenIndex = 1
        if 'page' in query:
            if 'token' in query['page']:
                # For testing purposes, we return a token that is the same as the key
                tokenIndex = int(query['page']['token'])
                items = items[tokenIndex - 1 :]
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

    def EncryptAlpha1(self, requests: EncryptRequest, context):
        for req in requests:
            # mock encrypt operation by uppercasing the data
            req.payload.data = req.payload.data.upper()
            yield EncryptResponse(payload=req.payload)

    def DecryptAlpha1(self, requests: DecryptRequest, context):
        for req in requests:
            # mock decrypt operation by lowercasing the data
            req.payload.data = req.payload.data.lower()
            yield DecryptResponse(payload=req.payload)

    def StartWorkflowBeta1(self, request: StartWorkflowRequest, context):
        instance_id = request.instance_id

        if instance_id not in self.workflow_status:
            self.workflow_status[instance_id] = WorkflowRuntimeStatus.RUNNING
            return StartWorkflowResponse(instance_id=instance_id)
        else:
            # workflow already running
            raise Exception('Unable to start insance of the workflow')

    def GetWorkflowBeta1(self, request: GetWorkflowRequest, context):
        instance_id = request.instance_id

        if instance_id in self.workflow_status:
            status = str(self.workflow_status[instance_id])[len('WorkflowRuntimeStatus.') :]
            return GetWorkflowResponse(
                instance_id=instance_id,
                workflow_name='example',
                created_at=None,
                last_updated_at=None,
                runtime_status=status,
                properties=self.workflow_options,
            )
        else:
            # workflow non-existent
            raise Exception('Workflow instance does not exist')

    def PauseWorkflowBeta1(self, request: PauseWorkflowRequest, context):
        instance_id = request.instance_id

        if instance_id in self.workflow_status:
            self.workflow_status[instance_id] = WorkflowRuntimeStatus.SUSPENDED
            return empty_pb2.Empty()
        else:
            # workflow non-existent
            raise Exception('Workflow instance could not be paused')

    def ResumeWorkflowBeta1(self, request: ResumeWorkflowRequest, context):
        instance_id = request.instance_id

        if instance_id in self.workflow_status:
            self.workflow_status[instance_id] = WorkflowRuntimeStatus.RUNNING
            return empty_pb2.Empty()
        else:
            # workflow non-existent
            raise Exception('Workflow instance could not be resumed')

    def TerminateWorkflowBeta1(self, request: TerminateWorkflowRequest, context):
        instance_id = request.instance_id

        if instance_id in self.workflow_status:
            self.workflow_status[instance_id] = WorkflowRuntimeStatus.TERMINATED
            return empty_pb2.Empty()
        else:
            # workflow non-existent
            raise Exception('Workflow instance could not be terminated')

    def PurgeWorkflowBeta1(self, request: PurgeWorkflowRequest, context):
        instance_id = request.instance_id

        if instance_id in self.workflow_status:
            del self.workflow_status[instance_id]
            return empty_pb2.Empty()
        else:
            # workflow non-existent
            raise Exception('Workflow instance could not be purged')

    def RaiseEventWorkflowBeta1(self, request: RaiseEventWorkflowRequest, context):
        instance_id = request.instance_id

        if instance_id in self.workflow_status:
            self.workflow_options[instance_id] = request.event_data
            return empty_pb2.Empty()
        else:
            raise Exception('Unable to raise event on workflow instance')

    def GetMetadata(self, request, context):
        self.check_for_exception(context)

        return GetMetadataResponse(
            id='myapp',
            active_actors_count=[
                ActiveActorsCount(
                    type='Nichelle Nichols',
                    count=1,
                ),
            ],
            registered_components=[
                RegisteredComponents(
                    name='lockstore',
                    type='lock.redis',
                    version='',
                    # Missing capabilities definition,
                ),
                RegisteredComponents(
                    name='pubsub', type='pubsub.redis', version='v1', capabilities=[]
                ),
                RegisteredComponents(
                    name='statestore',
                    type='state.redis',
                    version='v1',
                    capabilities=[
                        'ETAG',
                        'TRANSACTIONAL',
                        'ACTOR',
                    ],
                ),
            ],
            extended_metadata=self.metadata,
        )

    def SetMetadata(self, request: SetMetadataRequest, context):
        self.metadata[request.key] = request.value
        return empty_pb2.Empty()

    def Shutdown(self, request, context):
        self.shutdown_received = True
        return empty_pb2.Empty()
