import json
from concurrent import futures
from typing import Dict, Optional, Tuple

import grpc
from google.protobuf import empty_pb2, struct_pb2
from google.protobuf.any_pb2 import Any as GrpcAny
from google.rpc import code_pb2, status_pb2
from grpc_status import rpc_status

from dapr.clients.grpc._helpers import to_bytes
from dapr.clients.grpc._response import WorkflowRuntimeStatus
from dapr.proto import api_service_v1, api_v1, appcallback_v1, common_v1
from dapr.proto.common.v1.common_pb2 import ConfigurationItem
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
        self.jobs: Dict[str, api_v1.Job] = {}
        self.job_overwrites: Dict[str, bool] = {}
        self._next_exception = None
        # When set, the next BulkPublishEvent call returns this many entries as failed.
        self._bulk_publish_fail_next: Optional[Tuple[int, str]] = None
        # When True, the next BulkPublishEvent (stable) call returns UNIMPLEMENTED; Alpha1 is unchanged.
        self._bulk_publish_stable_unimplemented_next: bool = False

    def set_bulk_publish_unimplemented_on_stable_next(self) -> None:
        """Make the next BulkPublishEvent (stable) call return UNIMPLEMENTED.

        BulkPublishEventAlpha1 is unchanged, so clients can fall back to Alpha1 and succeed.
        Useful for testing the UNIMPLEMENTED fallback path in publish_events.
        """
        self._bulk_publish_stable_unimplemented_next = True

    def set_bulk_publish_failed_entries_on_next_call(
        self, failed_entry_count: int = 1, error_message: str = 'simulated failure'
    ) -> None:
        """Configure the next BulkPublishEvent/BulkPublishEventAlpha1 call to return failed entries.

        The first failed_entry_count entries from the request will be reported as failed.
        Useful for testing BulkPublishResponse with non-empty failed_entries.
        """
        self._bulk_publish_fail_next = (failed_entry_count, error_message)

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

    def _bulk_publish_response(self, request) -> api_v1.BulkPublishResponse:
        if not self._bulk_publish_fail_next or not request.entries:
            return api_v1.BulkPublishResponse()
        count, error_message = self._bulk_publish_fail_next
        self._bulk_publish_fail_next = None
        failed = [
            api_v1.BulkPublishResponseFailedEntry(
                entry_id=entry.entry_id,
                error=error_message,
            )
            for entry in request.entries[:count]
        ]
        return api_v1.BulkPublishResponse(failedEntries=failed)

    def BulkPublishEvent(self, request, context):
        if self._bulk_publish_stable_unimplemented_next:
            self._bulk_publish_stable_unimplemented_next = False
            context.abort_with_status(
                rpc_status.to_status(
                    status_pb2.Status(
                        code=code_pb2.UNIMPLEMENTED,
                        message='BulkPublishEvent not implemented',
                    )
                )
            )
        self.check_for_exception(context)
        return self._bulk_publish_response(request)

    def BulkPublishEventAlpha1(self, request, context):
        self.check_for_exception(context)
        return self._bulk_publish_response(request)

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
            api_v1.QueryStateItem(key=str(key), data=bytes('value of ' + str(key), 'UTF-8'))
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

    def TryLockAlpha1(self, request: api_v1.TryLockRequest, context):
        lock_id = (request.store_name, request.resource_id)

        if lock_id not in self.locks_to_owner:
            self.locks_to_owner[lock_id] = request.lock_owner
            return api_v1.TryLockResponse(success=True)
        else:
            # Lock already acquired
            return api_v1.TryLockResponse(success=False)

    def UnlockAlpha1(self, request: api_v1.UnlockRequest, context):
        lock_id = (request.store_name, request.resource_id)

        if lock_id not in self.locks_to_owner:
            return api_v1.UnlockResponse(status=api_v1.UnlockResponse.Status.LOCK_DOES_NOT_EXIST)
        elif self.locks_to_owner[lock_id] == request.lock_owner:
            del self.locks_to_owner[lock_id]
            return api_v1.UnlockResponse(status=api_v1.UnlockResponse.Status.SUCCESS)
        else:
            return api_v1.UnlockResponse(status=api_v1.UnlockResponse.Status.LOCK_BELONGS_TO_OTHERS)

    def EncryptAlpha1(self, requests: api_v1.EncryptRequest, context):
        for req in requests:
            # mock encrypt operation by uppercasing the data
            req.payload.data = req.payload.data.upper()
            yield api_v1.EncryptResponse(payload=req.payload)

    def DecryptAlpha1(self, requests: api_v1.DecryptRequest, context):
        for req in requests:
            # mock decrypt operation by lowercasing the data
            req.payload.data = req.payload.data.lower()
            yield api_v1.DecryptResponse(payload=req.payload)

    def StartWorkflowBeta1(self, request: api_v1.StartWorkflowRequest, context):
        instance_id = request.instance_id

        if instance_id not in self.workflow_status:
            self.workflow_status[instance_id] = WorkflowRuntimeStatus.RUNNING
            return api_v1.StartWorkflowResponse(instance_id=instance_id)
        else:
            # workflow already running
            raise Exception('Unable to start insance of the workflow')

    def GetWorkflowBeta1(self, request: api_v1.GetWorkflowRequest, context):
        instance_id = request.instance_id

        if instance_id in self.workflow_status:
            status = str(self.workflow_status[instance_id])[len('WorkflowRuntimeStatus.') :]
            return api_v1.GetWorkflowResponse(
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

    def PauseWorkflowBeta1(self, request: api_v1.PauseWorkflowRequest, context):
        instance_id = request.instance_id

        if instance_id in self.workflow_status:
            self.workflow_status[instance_id] = WorkflowRuntimeStatus.SUSPENDED
            return empty_pb2.Empty()
        else:
            # workflow non-existent
            raise Exception('Workflow instance could not be paused')

    def ResumeWorkflowBeta1(self, request: api_v1.ResumeWorkflowRequest, context):
        instance_id = request.instance_id

        if instance_id in self.workflow_status:
            self.workflow_status[instance_id] = WorkflowRuntimeStatus.RUNNING
            return empty_pb2.Empty()
        else:
            # workflow non-existent
            raise Exception('Workflow instance could not be resumed')

    def TerminateWorkflowBeta1(self, request: api_v1.TerminateWorkflowRequest, context):
        instance_id = request.instance_id

        if instance_id in self.workflow_status:
            self.workflow_status[instance_id] = WorkflowRuntimeStatus.TERMINATED
            return empty_pb2.Empty()
        else:
            # workflow non-existent
            raise Exception('Workflow instance could not be terminated')

    def PurgeWorkflowBeta1(self, request: api_v1.PurgeWorkflowRequest, context):
        instance_id = request.instance_id

        if instance_id in self.workflow_status:
            del self.workflow_status[instance_id]
            return empty_pb2.Empty()
        else:
            # workflow non-existent
            raise Exception('Workflow instance could not be purged')

    def RaiseEventWorkflowBeta1(self, request: api_v1.RaiseEventWorkflowRequest, context):
        instance_id = request.instance_id

        if instance_id in self.workflow_status:
            self.workflow_options[instance_id] = request.event_data
            return empty_pb2.Empty()
        else:
            raise Exception('Unable to raise event on workflow instance')

    def GetMetadata(self, request, context):
        self.check_for_exception(context)

        return api_v1.GetMetadataResponse(
            id='myapp',
            active_actors_count=[
                api_v1.ActiveActorsCount(
                    type='Nichelle Nichols',
                    count=1,
                ),
            ],
            registered_components=[
                api_v1.RegisteredComponents(
                    name='lockstore',
                    type='lock.redis',
                    version='',
                    # Missing capabilities definition,
                ),
                api_v1.RegisteredComponents(
                    name='pubsub', type='pubsub.redis', version='v1', capabilities=[]
                ),
                api_v1.RegisteredComponents(
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

    def ConverseAlpha1(self, request, context):
        """Mock implementation of the ConverseAlpha1 endpoint."""
        self.check_for_exception(context)

        # Echo back the input messages as outputs
        outputs = []
        for input in request.inputs:
            result = f'Response to: {input.content}'
            outputs.append(api_v1.ConversationResult(result=result, parameters={}))

        return api_v1.ConversationResponse(contextID=request.contextID, outputs=outputs)

    def ConverseAlpha2(self, request, context):
        """Mock implementation of the ConverseAlpha2 endpoint."""
        self.check_for_exception(context)

        # Process inputs and create responses with choices structure
        outputs = []
        for input_idx, input in enumerate(request.inputs):
            choices = []

            # Process each message in the input
            for msg_idx, message in enumerate(input.messages):
                response_content = ''
                tool_calls = []

                # Extract content based on message type
                if message.HasField('of_user'):
                    if message.of_user.content:
                        response_content = f'Response to user: {message.of_user.content[0].text}'
                elif message.HasField('of_system'):
                    if message.of_system.content:
                        response_content = (
                            f'System acknowledged: {message.of_system.content[0].text}'
                        )
                elif message.HasField('of_assistant'):
                    if message.of_assistant.content:
                        response_content = (
                            f'Assistant continued: {message.of_assistant.content[0].text}'
                        )
                elif message.HasField('of_developer'):
                    if message.of_developer.content:
                        response_content = (
                            f'Developer note processed: {message.of_developer.content[0].text}'
                        )
                elif message.HasField('of_tool'):
                    if message.of_tool.content:
                        response_content = (
                            f'Tool result processed: {message.of_tool.content[0].text}'
                        )

                # Check if tools are available and simulate tool calling
                if request.tools and response_content and 'weather' in response_content.lower():
                    # Simulate a tool call for weather requests
                    for tool in request.tools:
                        if tool.function and 'weather' in tool.function.name.lower():
                            tool_call = api_v1.ConversationToolCalls(
                                id=f'call_{input_idx}_{msg_idx}',
                                function=api_v1.ConversationToolCallsOfFunction(
                                    name=tool.function.name,
                                    arguments='{"location": "San Francisco", "unit": "celsius"}',
                                ),
                            )
                            tool_calls.append(tool_call)
                            response_content = "I'll check the weather for you."
                            break

                # Create result message
                result_message = api_v1.ConversationResultMessage(
                    content=response_content, tool_calls=tool_calls
                )

                # Create choice
                finish_reason = 'tool_calls' if tool_calls else 'stop'
                choice = api_v1.ConversationResultChoices(
                    finish_reason=finish_reason, index=msg_idx, message=result_message
                )
                choices.append(choice)

            # Create result for this input
            result = api_v1.ConversationResultAlpha2(choices=choices)
            if hasattr(result, 'model'):
                result.model = 'test-llm'
            if hasattr(result, 'usage'):
                try:
                    usage_cls = getattr(api_v1, 'ConversationResultAlpha2CompletionUsage', None)
                    if usage_cls is not None:
                        u = usage_cls(
                            completion_tokens=10,
                            prompt_tokens=5,
                            total_tokens=15,
                        )
                        result.usage.CopyFrom(u)
                except Exception:
                    pass
            outputs.append(result)

        return api_v1.ConversationResponseAlpha2(
            context_id=request.context_id if request.HasField('context_id') else None,
            outputs=outputs,
        )

    def ScheduleJobAlpha1(self, request, context):
        self.check_for_exception(context)

        # Validate job name
        if not request.job.name:
            raise ValueError('Job name is required')

        # Validate job name
        if not request.job.schedule and not request.job.due_time:
            raise ValueError('Schedule is empty')

        # Store the job
        self.jobs[request.job.name] = request.job
        self.job_overwrites[request.job.name] = request.overwrite

        return empty_pb2.Empty()

    def GetJobAlpha1(self, request, context):
        self.check_for_exception(context)

        # Validate job name
        if not request.name:
            raise ValueError('Job name is required')

        # Check if job exists
        if request.name not in self.jobs:
            raise Exception(f'Job "{request.name}" not found')

        return api_v1.GetJobResponse(job=self.jobs[request.name])

    def DeleteJobAlpha1(self, request, context):
        self.check_for_exception(context)

        # Validate job name
        if not request.name:
            raise ValueError('Job name is required')

        # Check if job exists (optional - some implementations might not error)
        if request.name in self.jobs:
            del self.jobs[request.name]

        return empty_pb2.Empty()

    def SetMetadata(self, request: api_v1.SetMetadataRequest, context):
        self.metadata[request.key] = request.value
        return empty_pb2.Empty()

    def Shutdown(self, request, context):
        self.shutdown_received = True
        return empty_pb2.Empty()
