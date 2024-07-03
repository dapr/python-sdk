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

import time
import socket
import json
import uuid

from urllib.parse import urlencode

from warnings import warn

from typing import Callable, Dict, Optional, Text, Union, Sequence, List, Any
from typing_extensions import Self
from datetime import datetime
from google.protobuf.message import Message as GrpcMessage
from google.protobuf.empty_pb2 import Empty as GrpcEmpty

import grpc  # type: ignore
from grpc import (  # type: ignore
    UnaryUnaryClientInterceptor,
    UnaryStreamClientInterceptor,
    StreamUnaryClientInterceptor,
    StreamStreamClientInterceptor,
    RpcError,
)

from dapr.clients.exceptions import DaprInternalError, DaprGrpcError
from dapr.clients.grpc._state import StateOptions, StateItem
from dapr.clients.grpc._helpers import getWorkflowRuntimeStatus
from dapr.clients.grpc._crypto import EncryptOptions, DecryptOptions
from dapr.clients.grpc.interceptors import DaprClientInterceptor, DaprClientTimeoutInterceptor
from dapr.clients.health import DaprHealth
from dapr.clients.retry import RetryPolicy
from dapr.conf import settings
from dapr.proto import api_v1, api_service_v1, common_v1
from dapr.proto.runtime.v1.dapr_pb2 import UnsubscribeConfigurationResponse
from dapr.version import __version__

from dapr.clients.grpc._helpers import (
    MetadataTuple,
    to_bytes,
    validateNotNone,
    validateNotBlankString,
)
from dapr.conf.helpers import GrpcEndpoint
from dapr.clients.grpc._request import (
    InvokeMethodRequest,
    BindingRequest,
    TransactionalStateOperation,
    EncryptRequestIterator,
    DecryptRequestIterator,
)
from dapr.clients.grpc._response import (
    BindingResponse,
    DaprResponse,
    GetSecretResponse,
    GetBulkSecretResponse,
    GetMetadataResponse,
    InvokeMethodResponse,
    UnlockResponseStatus,
    StateResponse,
    BulkStatesResponse,
    BulkStateItem,
    ConfigurationResponse,
    QueryResponse,
    QueryResponseItem,
    RegisteredComponents,
    ConfigurationWatcher,
    TryLockResponse,
    UnlockResponse,
    GetWorkflowResponse,
    StartWorkflowResponse,
    EncryptResponse,
    DecryptResponse,
)


class DaprGrpcClient:
    """The convenient layer implementation of Dapr gRPC APIs.

    This provides the wrappers and helpers to allows developers to use Dapr runtime gRPC API
    easily and consistently.

    Examples:

        >>> from dapr.clients import DaprClient
        >>> d = DaprClient()
        >>> resp = d.invoke_method('callee', 'method', b'data')

    With context manager and custom message size limit:

        >>> from dapr.clients import DaprClient
        >>> MAX = 64 * 1024 * 1024 # 64MB
        >>> with DaprClient(max_message_length=MAX) as d:
        ...     resp = d.invoke_method('callee', 'method', b'data')
    """

    def __init__(
        self,
        address: Optional[str] = None,
        interceptors: Optional[
            List[
                Union[
                    UnaryUnaryClientInterceptor,
                    UnaryStreamClientInterceptor,
                    StreamUnaryClientInterceptor,
                    StreamStreamClientInterceptor,
                ]
            ]
        ] = None,
        max_grpc_message_length: Optional[int] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        """Connects to Dapr Runtime and initializes gRPC client stub.

        Args:
            address (str, optional): Dapr Runtime gRPC endpoint address.
            interceptors (list of UnaryUnaryClientInterceptor or
                UnaryStreamClientInterceptor or
                StreamUnaryClientInterceptor or
                StreamStreamClientInterceptor, optional): gRPC interceptors.
            max_grpc_message_length (int, optional): The maximum grpc send and receive
                message length in bytes.
            retry_policy (RetryPolicy optional): Specifies retry behaviour
        """
        DaprHealth.wait_until_ready()
        self.retry_policy = retry_policy or RetryPolicy()

        useragent = f'dapr-sdk-python/{__version__}'
        if not max_grpc_message_length:
            options = [
                ('grpc.primary_user_agent', useragent),
            ]
        else:
            options = [
                ('grpc.max_send_message_length', max_grpc_message_length),  # type: ignore
                ('grpc.max_receive_message_length', max_grpc_message_length),  # type: ignore
                ('grpc.primary_user_agent', useragent),
            ]

        if not address:
            address = settings.DAPR_GRPC_ENDPOINT or (
                f'{settings.DAPR_RUNTIME_HOST}:' f'{settings.DAPR_GRPC_PORT}'
            )

        try:
            self._uri = GrpcEndpoint(address)
        except ValueError as error:
            raise DaprInternalError(f'{error}') from error

        if self._uri.tls:
            self._channel = grpc.secure_channel(  # type: ignore
                self._uri.endpoint,
                self.get_credentials(),
                options=options,
            )
        else:
            self._channel = grpc.insecure_channel(  # type: ignore
                self._uri.endpoint,
                options=options,
            )

        self._channel = grpc.intercept_channel(self._channel, DaprClientTimeoutInterceptor())  # type: ignore

        if settings.DAPR_API_TOKEN:
            api_token_interceptor = DaprClientInterceptor(
                [
                    ('dapr-api-token', settings.DAPR_API_TOKEN),
                ]
            )
            self._channel = grpc.intercept_channel(  # type: ignore
                self._channel, api_token_interceptor
            )
        if interceptors:
            self._channel = grpc.intercept_channel(  # type: ignore
                self._channel, *interceptors
            )

        self._stub = api_service_v1.DaprStub(self._channel)

    @staticmethod
    def get_credentials():
        # This method is used (overwritten) from tests
        # to return credentials for self-signed certificates
        return grpc.ssl_channel_credentials()  # type: ignore

    def close(self):
        """Closes Dapr runtime gRPC channel."""
        if hasattr(self, '_channel') and self._channel:
            self._channel.close()

    def __del__(self):
        self.close()

    def __enter__(self) -> Self:  # type: ignore
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    @staticmethod
    def _get_http_extension(
        http_verb: str, http_querystring: Optional[MetadataTuple] = None
    ) -> common_v1.HTTPExtension:  # type: ignore
        verb = common_v1.HTTPExtension.Verb.Value(http_verb)  # type: ignore
        http_ext = common_v1.HTTPExtension(verb=verb)
        if http_querystring is not None and len(http_querystring):
            http_ext.querystring = urlencode(http_querystring)
        return http_ext

    def invoke_method(
        self,
        app_id: str,
        method_name: str,
        data: Union[bytes, str, GrpcMessage] = '',
        content_type: Optional[str] = None,
        metadata: Optional[MetadataTuple] = None,
        http_verb: Optional[str] = None,
        http_querystring: Optional[MetadataTuple] = None,
        timeout: Optional[int] = None,
    ) -> InvokeMethodResponse:
        """Invokes the target service to call method.

        This can invoke the specified target service to call method with bytes array data or
        custom protocol buffer message. If your callee application uses http appcallback,
        http_verb and http_querystring must be specified. Otherwise, Dapr runtime will return
        error.

        The example calls `callee` service with bytes data, which implements grpc appcallback:

            from dapr.clients import DaprClient

            with DaprClient() as d:
                resp = d.invoke_method(
                    app_id='callee',
                    method_name='method',
                    data=b'message',
                    content_type='text/plain',
                )

                # resp.content includes the content in bytes.
                # resp.content_type specifies the content type of resp.content.
                # Thus, resp.content can be deserialized properly.

        When sending custom protocol buffer message object, it doesn't requires content_type:

            from dapr.clients import DaprClient

            req_data = dapr_example_v1.CustomRequestMessage(data='custom')

            with DaprClient() as d:
                resp = d.invoke_method(
                    app_id='callee',
                    method_name='method',
                    data=req_data,
                )
                # Create protocol buffer object
                resp_data = dapr_example_v1.CustomResponseMessage()
                # Deserialize to resp_data
                resp.unpack(resp_data)

        The example calls `callee` service which implements http appcallback:

            from dapr.clients import DaprClient

            with DaprClient() as d:
                resp = d.invoke_method(
                    app_id='callee',
                    method_name='method',
                    data=b'message',
                    content_type='text/plain',
                    http_verb='POST',
                    http_querystring=(
                        ('key1', 'value1')
                    ),
                )

                # resp.content includes the content in bytes.
                # resp.content_type specifies the content type of resp.content.
                # Thus, resp.content can be deserialized properly.

        Args:
            app_id (str): the callee app id
            method (str): the method name which is called
            data (bytes or :obj:`google.protobuf.message.Message`, optional): bytes
                or Message for data which will be sent to app id
            metadata (tuple, optional, DEPRECATED): gRPC custom metadata
            http_verb (str, optional): http method verb to call HTTP callee application
            http_querystring (tuple, optional): the tuple to represent query string
            timeout (int, optional): request timeout in seconds

        Returns:
            :class:`InvokeMethodResponse` object returned from callee
        """
        warn(
            'invoke_method with protocol gRPC is deprecated. Use gRPC proxying instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        if metadata is not None:
            warn(
                'metadata argument is deprecated. Dapr already intercepts API token headers '
                'and this is not needed.',
                DeprecationWarning,
                stacklevel=2,
            )

        req_data = InvokeMethodRequest(data, content_type)
        http_ext = None
        if http_verb:
            http_ext = self._get_http_extension(http_verb, http_querystring)

        content_type = ''
        if req_data.content_type:
            content_type = req_data.content_type
        req = api_v1.InvokeServiceRequest(
            id=app_id,
            message=common_v1.InvokeRequest(
                method=method_name,
                data=req_data.proto,
                content_type=content_type,
                http_extension=http_ext,
            ),
        )

        response, call = self.retry_policy.run_rpc(
            self._stub.InvokeService.with_call, req, metadata=metadata, timeout=timeout
        )

        resp_data = InvokeMethodResponse(response.data, response.content_type)
        resp_data.headers = call.initial_metadata()  # type: ignore
        return resp_data

    def invoke_binding(
        self,
        binding_name: str,
        operation: str,
        data: Union[bytes, str] = '',
        binding_metadata: Dict[str, str] = {},
        metadata: Optional[MetadataTuple] = None,
    ) -> BindingResponse:
        """Invokes the output binding with the specified operation.

        The data field takes any JSON serializable value and acts as the
        payload to be sent to the output binding. The metadata field is an
        array of key/value pairs and allows you to set binding specific metadata
        for each call. The operation field tells the Dapr binding which operation
        it should perform.

        The example calls output `binding` service with bytes data:

            from dapr.clients import DaprClient

            with DaprClient() as d:
                resp = d.invoke_binding(
                    binding_name = 'kafkaBinding',
                    operation = 'create',
                    data = b'message',
                )
                # resp.data includes the response data in bytes.

        Args:
            binding_name (str): the name of the binding as defined in the components
            operation (str): the operation to perform on the binding
            data (bytes or str, optional): bytes or str for data which will sent to the binding
            binding_metadata (dict, optional): Dapr metadata for output binding
            metadata (tuple, optional, DEPRECATED): gRPC custom metadata

        Returns:
            :class:`InvokeBindingResponse` object returned from binding
        """
        if metadata is not None:
            warn(
                'metadata argument is deprecated. Dapr already intercepts API token headers '
                'and this is not needed.',
                DeprecationWarning,
                stacklevel=2,
            )

        req_data = BindingRequest(data, binding_metadata)

        req = api_v1.InvokeBindingRequest(
            name=binding_name,
            data=req_data.data,
            metadata=req_data.binding_metadata,
            operation=operation,
        )

        response, call = self.retry_policy.run_rpc(
            self._stub.InvokeBinding.with_call, req, metadata=metadata
        )
        return BindingResponse(response.data, dict(response.metadata), call.initial_metadata())

    def publish_event(
        self,
        pubsub_name: str,
        topic_name: str,
        data: Union[bytes, str],
        publish_metadata: Dict[str, str] = {},
        metadata: Optional[MetadataTuple] = None,
        data_content_type: Optional[str] = None,
    ) -> DaprResponse:
        """Publish to a given topic.
        This publishes an event with bytes array or str data to a specified topic and
        specified pubsub component. The str data is encoded into bytes with default
        charset of utf-8. Custom metadata can be passed with the metadata field which
        will be passed on a gRPC metadata.

        The example publishes a byte array event to a topic:

            from dapr.clients import DaprClient
            with DaprClient() as d:
                resp = d.publish_event(
                    pubsub_name='pubsub_1',
                    topic_name='TOPIC_A',
                    data=b'message',
                    publish_metadata={'ttlInSeconds': '100', 'rawPayload': 'false'},
                )
                # resp.headers includes the gRPC initial metadata.

        Args:
            pubsub_name (str): the name of the pubsub component
            topic_name (str): the topic name to publish to
            data (bytes or str): bytes or str for data
            publish_metadata (Dict[str, str], optional): Dapr metadata per Pub/Sub message
            metadata (tuple, optional, DEPRECATED): gRPC custom metadata
            data_content_type: (str, optional): content type of the data payload

        Returns:
            :class:`DaprResponse` gRPC metadata returned from callee
        """
        if metadata is not None:
            warn(
                'metadata argument is deprecated. Dapr already intercepts API token headers '
                'and this is not needed.',
                DeprecationWarning,
                stacklevel=2,
            )

        if not isinstance(data, bytes) and not isinstance(data, str):
            raise ValueError(f'invalid type for data {type(data)}')

        req_data: bytes
        if isinstance(data, bytes):
            req_data = data
        else:
            if isinstance(data, str):
                req_data = data.encode('utf-8')

        content_type = ''
        if data_content_type:
            content_type = data_content_type
        req = api_v1.PublishEventRequest(
            pubsub_name=pubsub_name,
            topic=topic_name,
            data=req_data,
            data_content_type=content_type,
            metadata=publish_metadata,
        )

        try:
            # response is google.protobuf.Empty
            _, call = self.retry_policy.run_rpc(
                self._stub.PublishEvent.with_call, req, metadata=metadata
            )
        except RpcError as err:
            raise DaprGrpcError(err) from err

        return DaprResponse(call.initial_metadata())

    def get_state(
        self,
        store_name: str,
        key: str,
        state_metadata: Optional[Dict[str, str]] = dict(),
        metadata: Optional[MetadataTuple] = None,
    ) -> StateResponse:
        """Gets value from a statestore with a key

        The example gets value from a statestore:
            from dapr.clients import DaprClient
            with DaprClient() as d:
                resp = d.get_state(
                    store_name='state_store'
                    key='key_1',
                    state={"key": "value"},
                    state_metadata={"metakey": "metavalue"},
                )

        Args:
            store_name (str): the state store name to get from
            key (str): the key of the key-value pair to be gotten
            state_metadata (Dict[str, str], optional): Dapr metadata for state request
            metadata (tuple, optional, DEPRECATED): gRPC custom metadata

        Returns:
            :class:`StateResponse` gRPC metadata returned from callee
            and value obtained from the state store
        """
        if metadata is not None:
            warn(
                'metadata argument is deprecated. Dapr already intercepts API token headers '
                'and this is not needed.',
                DeprecationWarning,
                stacklevel=2,
            )

        if not store_name or len(store_name) == 0 or len(store_name.strip()) == 0:
            raise ValueError('State store name cannot be empty')
        req = api_v1.GetStateRequest(store_name=store_name, key=key, metadata=state_metadata)
        try:
            response, call = self.retry_policy.run_rpc(
                self._stub.GetState.with_call, req, metadata=metadata
            )
            return StateResponse(
                data=response.data, etag=response.etag, headers=call.initial_metadata()
            )
        except RpcError as err:
            raise DaprGrpcError(err) from err

    def get_bulk_state(
        self,
        store_name: str,
        keys: Sequence[str],
        parallelism: int = 1,
        states_metadata: Optional[Dict[str, str]] = dict(),
        metadata: Optional[MetadataTuple] = None,
    ) -> BulkStatesResponse:
        """Gets values from a statestore with keys

        The example gets value from a statestore:
            from dapr.clients import DaprClient
            with DaprClient() as d:
                resp = d.get_bulk_state(
                    store_name='state_store',
                    keys=['key_1', key_2],
                    parallelism=2,
                    states_metadata={"metakey": "metavalue"},
                )

        Args:
            store_name (str): the state store name to get from
            keys (Sequence[str]): the keys to be retrieved
            parallelism (int): number of items to be retrieved in parallel
            states_metadata (Dict[str, str], optional): Dapr metadata for state request
            metadata (tuple, optional, DEPRECATED): gRPC custom metadata

        Returns:
            :class:`BulkStatesResponse` gRPC metadata returned from callee
            and value obtained from the state store
        """
        if metadata is not None:
            warn(
                'metadata argument is deprecated. Dapr already intercepts API token headers '
                'and this is not needed.',
                DeprecationWarning,
                stacklevel=2,
            )

        if not store_name or len(store_name) == 0 or len(store_name.strip()) == 0:
            raise ValueError('State store name cannot be empty')
        req = api_v1.GetBulkStateRequest(
            store_name=store_name, keys=keys, parallelism=parallelism, metadata=states_metadata
        )

        try:
            response, call = self.retry_policy.run_rpc(
                self._stub.GetBulkState.with_call, req, metadata=metadata
            )
        except RpcError as err:
            raise DaprGrpcError(err) from err

        items = []
        for item in response.items:
            items.append(
                BulkStateItem(key=item.key, data=item.data, etag=item.etag, error=item.error)
            )
        return BulkStatesResponse(items=items, headers=call.initial_metadata())

    def query_state(
        self, store_name: str, query: str, states_metadata: Optional[Dict[str, str]] = dict()
    ) -> QueryResponse:
        """Queries a statestore with a query

        For details on supported queries see https://docs.dapr.io/

        This example queries a statestore:
            from dapr.clients import DaprClient

            query = '''
            {
                "filter": {
                    "EQ": { "state": "CA" }
                },
                "sort": [
                    {
                        "key": "person.id",
                        "order": "DESC"
                    }
                ]
            }
            '''

            with DaprClient() as d:
                resp = d.query_state(
                    store_name='state_store',
                    query=query,
                    states_metadata={"metakey": "metavalue"},
                )

        Args:
            store_name (str): the state store name to query
            query (str): the query to be executed
            states_metadata (Dict[str, str], optional): custom metadata for state request

        Returns:
            :class:`QueryStateResponse` gRPC metadata returned from callee,
                pagination token and results of the query
        """
        warn(
            'The State Store Query API is an Alpha version and is subject to change.',
            UserWarning,
            stacklevel=2,
        )

        if not store_name or len(store_name) == 0 or len(store_name.strip()) == 0:
            raise ValueError('State store name cannot be empty')
        req = api_v1.QueryStateRequest(store_name=store_name, query=query, metadata=states_metadata)

        try:
            response, call = self.retry_policy.run_rpc(self._stub.QueryStateAlpha1.with_call, req)
        except RpcError as err:
            raise DaprGrpcError(err) from err

        results = []
        for item in response.results:
            results.append(
                QueryResponseItem(key=item.key, value=item.data, etag=item.etag, error=item.error)
            )

        return QueryResponse(
            token=response.token,
            results=results,
            metadata=response.metadata,
            headers=call.initial_metadata(),
        )

    def save_state(
        self,
        store_name: str,
        key: str,
        value: Union[bytes, str],
        etag: Optional[str] = None,
        options: Optional[StateOptions] = None,
        state_metadata: Optional[Dict[str, str]] = dict(),
        metadata: Optional[MetadataTuple] = None,
    ) -> DaprResponse:
        """Saves key-value pairs to a statestore

        This saves a value to the statestore with a given key and state store name.
        Options for request can be passed with the options field and custom
        metadata can be passed with metadata field.

        The example saves states to a statestore:
            from dapr.clients import DaprClient
            with DaprClient() as d:
                resp = d.save_state(
                    store_name='state_store',
                    key='key1',
                    value='value1',
                    etag='etag',
                    state_metadata={"metakey": "metavalue"},
                )

        Args:
            store_name (str): the state store name to save to
            key (str): the key to be saved
            value (bytes or str): the value to be saved
            etag (str, optional): the etag to save with
            options (StateOptions, optional): custom options
                for concurrency and consistency
            state_metadata (Dict[str, str], optional): Dapr metadata for state request
            metadata (tuple, optional, DEPRECATED): gRPC custom metadata

        Returns:
            :class:`DaprResponse` gRPC metadata returned from callee

        Raises:
            ValueError: value is not bytes or str
            ValueError: store_name is empty
        """
        if metadata is not None:
            warn(
                'metadata argument is deprecated. Dapr already intercepts API token headers '
                'and this is not needed.',
                DeprecationWarning,
                stacklevel=2,
            )

        if not isinstance(value, (bytes, str)):
            raise ValueError(f'invalid type for data {type(value)}')

        req_value = value

        if not store_name or len(store_name) == 0 or len(store_name.strip()) == 0:
            raise ValueError('State store name cannot be empty')

        if options is None:
            state_options = None
        else:
            state_options = options.get_proto()

        state = common_v1.StateItem(
            key=key,
            value=to_bytes(req_value),
            etag=common_v1.Etag(value=etag) if etag is not None else None,
            options=state_options,
            metadata=state_metadata,
        )

        req = api_v1.SaveStateRequest(store_name=store_name, states=[state])
        try:
            _, call = self.retry_policy.run_rpc(
                self._stub.SaveState.with_call, req, metadata=metadata
            )
            return DaprResponse(headers=call.initial_metadata())
        except RpcError as err:
            raise DaprGrpcError(err) from err

    def save_bulk_state(
        self, store_name: str, states: List[StateItem], metadata: Optional[MetadataTuple] = None
    ) -> DaprResponse:
        """Saves state items to a statestore

        This saves a given state item into the statestore specified by store_name.

        The example saves states to a statestore:
            from dapr.clients import DaprClient
            with DaprClient() as d:
                resp = d.save_bulk_state(
                    store_name='state_store',
                    states=[StateItem(key='key1', value='value1'),
                        StateItem(key='key2', value='value2', etag='etag'),],
                )

        Args:
            store_name (str): the state store name to save to
            states (List[StateItem]): list of states to save
            metadata (tuple, optional): gRPC custom metadata

        Returns:
            :class:`DaprResponse` gRPC metadata returned from callee

        Raises:
            ValueError: states is empty
            ValueError: store_name is empty
        """
        if metadata is not None:
            warn(
                'metadata argument is deprecated. Dapr already intercepts API token headers '
                'and this is not needed.',
                DeprecationWarning,
                stacklevel=2,
            )

        if not states or len(states) == 0:
            raise ValueError('States to be saved cannot be empty')

        if not store_name or len(store_name) == 0 or len(store_name.strip()) == 0:
            raise ValueError('State store name cannot be empty')

        req_states = [
            common_v1.StateItem(
                key=i.key,
                value=to_bytes(i.value),
                etag=common_v1.Etag(value=i.etag) if i.etag is not None else None,
                options=i.options,
                metadata=i.metadata,
            )
            for i in states
        ]

        req = api_v1.SaveStateRequest(store_name=store_name, states=req_states)

        try:
            _, call = self.retry_policy.run_rpc(
                self._stub.SaveState.with_call, req, metadata=metadata
            )
            return DaprResponse(headers=call.initial_metadata())
        except RpcError as err:
            raise DaprGrpcError(err) from err

    def execute_state_transaction(
        self,
        store_name: str,
        operations: Sequence[TransactionalStateOperation],
        transactional_metadata: Optional[Dict[str, str]] = dict(),
        metadata: Optional[MetadataTuple] = None,
    ) -> DaprResponse:
        """Saves or deletes key-value pairs to a statestore as a transaction

        This saves or deletes key-values to the statestore as part of a single transaction,
        transaction_metadata is used for the transaction operation, while metadata is used
        for the GRPC call.

        The example saves states to a statestore:
            from dapr.clients import DaprClient
            with DaprClient() as d:
                resp = d.execute_state_transaction(
                    store_name='state_store',
                    operations=[
                        TransactionalStateOperation(key=key, data=value),
                        TransactionalStateOperation(key=another_key, data=another_value),
                        TransactionalStateOperation(
                            operation_type=TransactionOperationType.delete,
                            key=key_to_delete),
                    ],
                    transactional_metadata={"header1": "value1"},
                )

        Args:
            store_name (str): the state store name to save to
            operations (Sequence[TransactionalStateOperation]): the transaction operations
            transactional_metadata (Dict[str, str], optional): Dapr metadata for transaction
            metadata (tuple, optional, DEPRECATED): gRPC custom metadata

        Returns:
            :class:`DaprResponse` gRPC metadata returned from callee
        """
        if metadata is not None:
            warn(
                'metadata argument is deprecated. Dapr already intercepts API token headers '
                'and this is not needed.',
                DeprecationWarning,
                stacklevel=2,
            )

        if not store_name or len(store_name) == 0 or len(store_name.strip()) == 0:
            raise ValueError('State store name cannot be empty')
        req_ops = [
            api_v1.TransactionalStateOperation(
                operationType=o.operation_type.value,
                request=common_v1.StateItem(
                    key=o.key,
                    value=to_bytes(o.data),
                    etag=common_v1.Etag(value=o.etag) if o.etag is not None else None,
                ),
            )
            for o in operations
        ]

        req = api_v1.ExecuteStateTransactionRequest(
            storeName=store_name, operations=req_ops, metadata=transactional_metadata
        )

        try:
            _, call = self.retry_policy.run_rpc(
                self._stub.ExecuteStateTransaction.with_call, req, metadata=metadata
            )
            return DaprResponse(headers=call.initial_metadata())
        except RpcError as err:
            raise DaprGrpcError(err) from err

    def delete_state(
        self,
        store_name: str,
        key: str,
        etag: Optional[str] = None,
        options: Optional[StateOptions] = None,
        state_metadata: Optional[Dict[str, str]] = dict(),
        metadata: Optional[MetadataTuple] = None,
    ) -> DaprResponse:
        """Deletes key-value pairs from a statestore

        This deletes a value from the statestore with a given key and state store name.
        Options for request can be passed with the options field and custom
        metadata can be passed with metadata field.

        The example deletes states from a statestore:
            from dapr.clients import DaprClient
            with DaprClient() as d:
                resp = d.delete_state(
                    store_name='state_store',
                    key='key1',
                    etag='etag',
                    state_metadata={"header1": "value1"},
                )

        Args:
            store_name (str): the state store name to delete from
            key (str): the key of the key-value pair to delete
            etag (str, optional): the etag to delete with
            options (StateOptions, optional): custom options
                for concurrency and consistency
            state_metadata (Dict[str, str], optional): Dapr metadata for state request
            metadata (tuple, optional, DEPRECATED): gRPC custom metadata

        Returns:
            :class:`DaprResponse` gRPC metadata returned from callee
        """
        if metadata is not None:
            warn(
                'metadata argument is deprecated. Dapr already intercepts API token '
                'headers and this is not needed.',
                DeprecationWarning,
                stacklevel=2,
            )

        if not store_name or len(store_name) == 0 or len(store_name.strip()) == 0:
            raise ValueError('State store name cannot be empty')

        if options is None:
            state_options = None
        else:
            state_options = options.get_proto()

        etag_object = common_v1.Etag(value=etag) if etag is not None else None
        req = api_v1.DeleteStateRequest(
            store_name=store_name,
            key=key,
            etag=etag_object,
            options=state_options,
            metadata=state_metadata,
        )

        try:
            _, call = self.retry_policy.run_rpc(
                self._stub.DeleteState.with_call, req, metadata=metadata
            )
            return DaprResponse(headers=call.initial_metadata())
        except RpcError as err:
            raise DaprGrpcError(err) from err

    def get_secret(
        self,
        store_name: str,
        key: str,
        secret_metadata: Optional[Dict[str, str]] = {},
        metadata: Optional[MetadataTuple] = None,
    ) -> GetSecretResponse:
        """Get secret with a given key.

        This gets a secret from secret store with a given key and secret store name.
        Metadata for request can be passed with the secret_metadata field and custom
        metadata can be passed with metadata field.


        The example gets a secret from secret store:

            from dapr.clients import DaprClient

            with DaprClient() as d:
                resp = d.get_secret(
                    store_name='secretstoreA',
                    key='keyA',
                    secret_metadata={'header1', 'value1'}
                )

                # resp.headers includes the gRPC initial metadata.
                # resp.trailers includes that gRPC trailing metadata.

        Args:
            store_name (str): store name to get secret from
            key (str): str for key
            secret_metadata (Dict[str, str], Optional): Dapr metadata for secrets request
            metadata (MetadataTuple, optional, DEPRECATED): gRPC custom metadata

        Returns:
            :class:`GetSecretResponse` object with the secret and metadata returned from callee
        """
        if metadata is not None:
            warn(
                'metadata argument is deprecated. Dapr already intercepts API token '
                'headers and this is not needed.',
                DeprecationWarning,
                stacklevel=2,
            )

        req = api_v1.GetSecretRequest(store_name=store_name, key=key, metadata=secret_metadata)

        response, call = self.retry_policy.run_rpc(
            self._stub.GetSecret.with_call, req, metadata=metadata
        )

        return GetSecretResponse(secret=response.data, headers=call.initial_metadata())

    def get_bulk_secret(
        self,
        store_name: str,
        secret_metadata: Optional[Dict[str, str]] = {},
        metadata: Optional[MetadataTuple] = None,
    ) -> GetBulkSecretResponse:
        """Get all granted secrets.

        This gets all granted secrets from secret store.
        Metadata for request can be passed with the secret_metadata field.


        The example gets all secrets from secret store:

            from dapr.clients import DaprClient

            with DaprClient() as d:
                resp = d.get_bulk_secret(
                    store_name='secretstoreA',
                    secret_metadata={'header1', 'value1'}
                )

                # resp.headers includes the gRPC initial metadata.
                # resp.trailers includes that gRPC trailing metadata.

        Args:
            store_name (str): store name to get secret from
            secret_metadata (Dict[str, Dict[str, str]], Optional): Dapr metadata of secrets request
            metadata (MetadataTuple, optional, DEPRECATED): gRPC custom metadata

        Returns:
            :class:`GetBulkSecretResponse` object with secrets and metadata returned from callee
        """
        if metadata is not None:
            warn(
                'metadata argument is deprecated. Dapr already intercepts API token '
                'headers and this is not needed.',
                DeprecationWarning,
                stacklevel=2,
            )

        req = api_v1.GetBulkSecretRequest(store_name=store_name, metadata=secret_metadata)

        response, call = self.retry_policy.run_rpc(
            self._stub.GetBulkSecret.with_call, req, metadata=metadata
        )

        secrets_map = {}
        for key in response.data.keys():
            secret_response = response.data[key]
            secrets_submap = {}
            for subkey in secret_response.secrets.keys():
                secrets_submap[subkey] = secret_response.secrets[subkey]
            secrets_map[key] = secrets_submap

        return GetBulkSecretResponse(secrets=secrets_map, headers=call.initial_metadata())

    def get_configuration(
        self, store_name: str, keys: List[str], config_metadata: Optional[Dict[str, str]] = dict()
    ) -> ConfigurationResponse:
        """Gets value from a config store with a key

        The example gets value from a config store:
            from dapr.clients import DaprClient
            with DaprClient() as d:
                resp = d.get_configuration(
                    store_name='state_store'
                    keys=['key_1'],
                    config_metadata={"metakey": "metavalue"}
                )

        Args:
            store_name (str): the state store name to get from
            keys (List[str]): the keys of the key-value pairs to be gotten
            config_metadata (Dict[str, str], optional): Dapr metadata for configuration

        Returns:
            :class:`ConfigurationResponse` gRPC metadata returned from callee
            and value obtained from the config store
        """
        if not store_name or len(store_name) == 0 or len(store_name.strip()) == 0:
            raise ValueError('Config store name cannot be empty to get the configuration')
        req = api_v1.GetConfigurationRequest(
            store_name=store_name, keys=keys, metadata=config_metadata
        )
        response, call = self.retry_policy.run_rpc(self._stub.GetConfiguration.with_call, req)
        return ConfigurationResponse(items=response.items, headers=call.initial_metadata())

    def subscribe_configuration(
        self,
        store_name: str,
        keys: List[str],
        handler: Callable[[Text, ConfigurationResponse], None],
        config_metadata: Optional[Dict[str, str]] = dict(),
    ) -> Text:
        """Gets changed value from a config store with a key

        The example gets value from a config store:
            from dapr.clients import DaprClient
            with DaprClient() as d:
                resp = d.subscribe_configuration(
                    store_name='state_store'
                    keys=['key_1'],
                    handler=handler,
                    config_metadata={"metakey": "metavalue"}
                )

        Args:
            store_name (str): the state store name to get from
            keys (str array): the keys of the key-value pairs to be gotten
            handler(func (key, ConfigurationResponse)): the callback function to be called
            config_metadata (Dict[str, str], optional): Dapr metadata for configuration

        Returns:
            id (str): subscription id, which can be used to unsubscribe later
        """

        if not store_name or len(store_name) == 0 or len(store_name.strip()) == 0:
            raise ValueError('Config store name cannot be empty to get the configuration')

        configWatcher = ConfigurationWatcher()
        id = configWatcher.watch_configuration(
            self._stub, store_name, keys, handler, config_metadata
        )
        return id

    def unsubscribe_configuration(self, store_name: str, id: str) -> bool:
        """Unsubscribes from configuration changes.

        Args:
            store_name (str): the state store name to unsubscribe from
            id (str): the subscription id to unsubscribe

        Returns:
            bool: True if unsubscribed successfully, False otherwise
        """
        req = api_v1.UnsubscribeConfigurationRequest(store_name=store_name, id=id)
        response: UnsubscribeConfigurationResponse = self._stub.UnsubscribeConfiguration(req)
        return response.ok

    def try_lock(
        self, store_name: str, resource_id: str, lock_owner: str, expiry_in_seconds: int
    ) -> TryLockResponse:
        """Tries to get a lock with an expiry.

        You can use the result of this operation directly on an `if` statement:

            if client.try_lock(store_name, resource_id, first_client_id, expiry_s):
                # lock acquired successfully...

        You can also inspect the response's `success` attribute:

                response = client.try_lock(store_name, resource_id, first_client_id, expiry_s)
                if response.success:
                    # lock acquired successfully...

        Finally, you can use this response with a `with` statement, and have the lock
        be automatically unlocked after the with-statement scope ends

            with client.try_lock(store_name, resource_id, first_client_id, expiry_s) as lock:
                if lock:
                    # lock acquired successfully...
            # Lock automatically unlocked at this point, no need to call client->unlock(...)

        Args:
            store_name (str): the lock store name, e.g. `redis`.
            resource_id (str): the lock key. e.g. `order_id_111`.
                                It stands for "which resource I want to protect".
            lock_owner (str):  indicates the identifier of lock owner.
            expiry_in_seconds (int): The length of time (in seconds) for which this lock
                will be held and after which it expires.

        Returns:
            :class:`TryLockResponse`: With the result of the try-lock operation.
        """
        # Warnings and input validation
        warn(
            'The Distributed Lock API is an Alpha version and is subject to change.',
            UserWarning,
            stacklevel=2,
        )
        validateNotBlankString(
            store_name=store_name, resource_id=resource_id, lock_owner=lock_owner
        )
        if not expiry_in_seconds or expiry_in_seconds < 1:
            raise ValueError('expiry_in_seconds must be a positive number')
        # Actual tryLock invocation
        req = api_v1.TryLockRequest(
            store_name=store_name,
            resource_id=resource_id,
            lock_owner=lock_owner,
            expiry_in_seconds=expiry_in_seconds,
        )
        response, call = self.retry_policy.run_rpc(self._stub.TryLockAlpha1.with_call, req)
        return TryLockResponse(
            success=response.success,
            client=self,
            store_name=store_name,
            resource_id=resource_id,
            lock_owner=lock_owner,
            headers=call.initial_metadata(),
        )

    def unlock(self, store_name: str, resource_id: str, lock_owner: str) -> UnlockResponse:
        """Unlocks a lock.

        Args:
            store_name (str): the lock store name, e.g. `redis`.
            resource_id (str): the lock key. e.g. `order_id_111`.
                                It stands for "which resource I want to protect".
            lock_owner (str):  indicates the identifier of lock owner.
            metadata (tuple, optional, DEPRECATED): gRPC custom metadata

        Returns:
            :class:`UnlockResponseStatus`: Status of the request,
                `UnlockResponseStatus.success` if it was successful of some other
                status otherwise.
        """
        # Warnings and input validation
        warn(
            'The Distributed Lock API is an Alpha version and is subject to change.',
            UserWarning,
            stacklevel=2,
        )
        validateNotBlankString(
            store_name=store_name, resource_id=resource_id, lock_owner=lock_owner
        )
        # Actual unlocking invocation
        req = api_v1.UnlockRequest(
            store_name=store_name, resource_id=resource_id, lock_owner=lock_owner
        )
        response, call = self.retry_policy.run_rpc(self._stub.UnlockAlpha1.with_call, req)

        return UnlockResponse(
            status=UnlockResponseStatus(response.status), headers=call.initial_metadata()
        )

    def encrypt(self, data: Union[str, bytes], options: EncryptOptions):
        """Encrypt a stream data with given options.

        The encrypt API encrypts a stream data with the given options.

        Example:
            from dapr.clients import DaprClient
            from dapr.clients.grpc._crypto import EncryptOptions

            with DaprClient() as d:
                options = EncryptOptions(
                    component_name='crypto_component',
                    key_name='crypto_key',
                    key_wrap_algorithm='RSA',
                )
                resp = d.encrypt(
                    data='hello dapr',
                    options=options,
                )
                encrypted_data = resp.read()

        Args:
            data (Union[str, bytes]): Data to be encrypted.
            options (EncryptOptions): Encryption options.

        Returns:
            Readable stream of `api_v1.EncryptResponse`.

        Raises:
            ValueError: If component_name, key_name, or key_wrap_algorithm is empty.
        """
        # Warnings and input validation
        warn(
            'The Encrypt API is an Alpha version and is subject to change.',
            UserWarning,
            stacklevel=2,
        )
        validateNotBlankString(
            component_name=options.component_name,
            key_name=options.key_name,
            key_wrap_algorithm=options.key_wrap_algorithm,
        )

        req_iterator = EncryptRequestIterator(data, options)
        resp_stream = self._stub.EncryptAlpha1(req_iterator)
        return EncryptResponse(resp_stream)

    def decrypt(self, data: Union[str, bytes], options: DecryptOptions):
        """Decrypt a stream data with given options.

        The decrypt API decrypts a stream data with the given options.

        Example:
            from dapr.clients import DaprClient
            from dapr.clients.grpc._crypto import DecryptOptions

            with DaprClient() as d:
                options = DecryptOptions(
                    component_name='crypto_component',
                    key_name='crypto_key',
                )
                resp = d.decrypt(
                    data='hello dapr',
                    options=options,
                )
                decrypted_data = resp.read()

        Args:
            data (Union[str, bytes]): Data to be decrypted.
            options (DecryptOptions): Decryption options.

        Returns:
            Readable stream of `api_v1.DecryptResponse`.

        Raises:
            ValueError: If component_name is empty.
        """
        # Warnings and input validation
        warn(
            'The Decrypt API is an Alpha version and is subject to change.',
            UserWarning,
            stacklevel=2,
        )
        validateNotBlankString(
            component_name=options.component_name,
        )

        req_iterator = DecryptRequestIterator(data, options)
        resp_stream = self._stub.DecryptAlpha1(req_iterator)
        return DecryptResponse(resp_stream)

    def start_workflow(
        self,
        workflow_component: str,
        workflow_name: str,
        input: Optional[Union[Any, bytes]] = None,
        instance_id: Optional[str] = None,
        workflow_options: Optional[Dict[str, str]] = dict(),
        send_raw_bytes: bool = False,
    ) -> StartWorkflowResponse:
        """Starts a workflow.

        Args:
            workflow_component (str): the name of the workflow component
                                that will run the workflow. e.g. `dapr`.
            workflow_name (str): the name of the workflow that will be executed.
            input (Optional[Union[Any, bytes]]): the input that the workflow will receive.
                                             The input value will be serialized to JSON
                                             by default. Use the send_raw_bytes param
                                             to send unencoded binary input.
            instance_id (Optional[str]): the name of the workflow instance,
                                e.g. `order_processing_workflow-103784`.
            workflow_options (Optional[Dict[str, str]]): the key-value options
                                that the workflow will receive.
            send_raw_bytes (bool) if true, no serialization will be performed on the input
                                bytes

        Returns:
            :class:`StartWorkflowResponse`: Instance ID associated with the started workflow
        """
        # Warnings and input validation
        warn(
            'The Workflow API is a Beta version and is subject to change.',
            UserWarning,
            stacklevel=2,
        )
        validateNotBlankString(workflow_component=workflow_component, workflow_name=workflow_name)

        if instance_id is None:
            instance_id = str(uuid.uuid4())

        if isinstance(input, bytes) and send_raw_bytes:
            encoded_data = input
        else:
            try:
                encoded_data = json.dumps(input).encode('utf-8') if input is not None else bytes([])
            except TypeError:
                raise DaprInternalError('start_workflow: input data must be JSON serializable')
            except ValueError as e:
                raise DaprInternalError(f'start_workflow JSON serialization error: {e}')

        # Actual start workflow invocation
        req = api_v1.StartWorkflowRequest(
            instance_id=instance_id,
            workflow_component=workflow_component,
            workflow_name=workflow_name,
            options=workflow_options,
            input=encoded_data,
        )

        try:
            response = self._stub.StartWorkflowBeta1(req)
            return StartWorkflowResponse(instance_id=response.instance_id)
        except RpcError as err:
            raise DaprInternalError(err.details())

    def get_workflow(self, instance_id: str, workflow_component: str) -> GetWorkflowResponse:
        """Gets information on a workflow.

        Args:
            instance_id (str): the ID of the workflow instance,
                                e.g. `order_processing_workflow-103784`.
            workflow_component (str): the name of the workflow component
                                that will run the workflow. e.g. `dapr`.

        Returns:
            :class:`GetWorkflowResponse`: Instance ID associated with the started workflow
        """
        # Warnings and input validation
        warn(
            'The Workflow API is a Beta version and is subject to change.',
            UserWarning,
            stacklevel=2,
        )
        validateNotBlankString(instance_id=instance_id, workflow_component=workflow_component)
        # Actual get workflow invocation
        req = api_v1.GetWorkflowRequest(
            instance_id=instance_id, workflow_component=workflow_component
        )

        try:
            resp = self.retry_policy.run_rpc(self._stub.GetWorkflowBeta1, req)
            if resp.created_at is None:
                resp.created_at = datetime.now()
            if resp.last_updated_at is None:
                resp.last_updated_at = datetime.now()
            return GetWorkflowResponse(
                instance_id=instance_id,
                workflow_name=resp.workflow_name,
                created_at=resp.created_at,
                last_updated_at=resp.last_updated_at,
                runtime_status=getWorkflowRuntimeStatus(resp.runtime_status),
                properties=resp.properties,
            )
        except RpcError as err:
            raise DaprInternalError(err.details())

    def terminate_workflow(self, instance_id: str, workflow_component: str) -> DaprResponse:
        """Terminates a workflow.

            Args:
                instance_id (str): the ID of the workflow instance, e.g.
                                    `order_processing_workflow-103784`.
                workflow_component (str): the name of the workflow component
                                    that will run the workflow. e.g. `dapr`.

        Returns:
            :class:`DaprResponse` gRPC metadata returned from callee

        """
        # Warnings and input validation
        warn(
            'The Workflow API is a Beta version and is subject to change.',
            UserWarning,
            stacklevel=2,
        )
        validateNotBlankString(instance_id=instance_id, workflow_component=workflow_component)
        # Actual terminate workflow invocation
        req = api_v1.TerminateWorkflowRequest(
            instance_id=instance_id, workflow_component=workflow_component
        )

        try:
            _, call = self.retry_policy.run_rpc(self._stub.TerminateWorkflowBeta1.with_call, req)
            return DaprResponse(headers=call.initial_metadata())
        except RpcError as err:
            raise DaprInternalError(err.details())

    def raise_workflow_event(
        self,
        instance_id: str,
        workflow_component: str,
        event_name: str,
        event_data: Optional[Union[Any, bytes]] = None,
        send_raw_bytes: bool = False,
    ) -> DaprResponse:
        """Raises an event on a workflow.

        Args:
            instance_id (str): the ID of the workflow instance,
                                e.g. `order_processing_workflow-103784`.
            workflow_component (str): the name of the workflow component
                                that will run the workflow. e.g. `dapr`.
            event_data (Optional[Union[Any, bytes]]): the input that the workflow will receive.
                                             The input value will be serialized to JSON
                                             by default. Use the send_raw_bytes param
                                             to send unencoded binary input.
            event_data (Optional[Union[Any, bytes]]): the input to the event.
            send_raw_bytes (bool) if true, no serialization will be performed on the input
                                bytes

        Returns:
            :class:`DaprResponse` gRPC metadata returned from callee
        """
        # Warnings and input validation
        warn(
            'The Workflow API is a Beta version and is subject to change.',
            UserWarning,
            stacklevel=2,
        )
        validateNotBlankString(
            instance_id=instance_id, workflow_component=workflow_component, event_name=event_name
        )

        if isinstance(event_data, bytes) and send_raw_bytes:
            encoded_data = event_data
        else:
            if event_data is not None:
                try:
                    encoded_data = (
                        json.dumps(event_data).encode('utf-8')
                        if event_data is not None
                        else bytes([])
                    )
                except TypeError:
                    raise DaprInternalError(
                        'raise_workflow_event:\
                                             event_data must be JSON serializable'
                    )
                except ValueError as e:
                    raise DaprInternalError(f'raise_workflow_event JSON serialization error: {e}')
                encoded_data = json.dumps(event_data).encode('utf-8')
            else:
                encoded_data = bytes([])

        # Actual workflow raise event invocation
        req = api_v1.RaiseEventWorkflowRequest(
            instance_id=instance_id,
            workflow_component=workflow_component,
            event_name=event_name,
            event_data=encoded_data,
        )

        try:
            _, call = self.retry_policy.run_rpc(self._stub.RaiseEventWorkflowBeta1.with_call, req)
            return DaprResponse(headers=call.initial_metadata())
        except RpcError as err:
            raise DaprInternalError(err.details())

    def pause_workflow(self, instance_id: str, workflow_component: str) -> DaprResponse:
        """Pause a workflow.

            Args:
                instance_id (str): the ID of the workflow instance,
                                    e.g. `order_processing_workflow-103784`.
                workflow_component (str): the name of the workflow component
                                    that will run the workflow. e.g. `dapr`.

        Returns:
            :class:`DaprResponse` gRPC metadata returned from callee

        """
        # Warnings and input validation
        warn(
            'The Workflow API is a Beta version and is subject to change.',
            UserWarning,
            stacklevel=2,
        )
        validateNotBlankString(instance_id=instance_id, workflow_component=workflow_component)
        # Actual pause workflow invocation
        req = api_v1.PauseWorkflowRequest(
            instance_id=instance_id, workflow_component=workflow_component
        )

        try:
            _, call = self.retry_policy.run_rpc(self._stub.PauseWorkflowBeta1.with_call, req)

            return DaprResponse(headers=call.initial_metadata())
        except RpcError as err:
            raise DaprInternalError(err.details())

    def resume_workflow(self, instance_id: str, workflow_component: str) -> DaprResponse:
        """Resumes a workflow.

        Args:
            instance_id (str): the ID of the workflow instance,
                                e.g. `order_processing_workflow-103784`.
            workflow_component (str): the name of the workflow component
                                that will run the workflow. e.g. `dapr`.

        Returns:
            :class:`DaprResponse` gRPC metadata returned from callee
        """
        # Warnings and input validation
        warn(
            'The Workflow API is a Beta version and is subject to change.',
            UserWarning,
            stacklevel=2,
        )
        validateNotBlankString(instance_id=instance_id, workflow_component=workflow_component)
        # Actual resume workflow invocation
        req = api_v1.ResumeWorkflowRequest(
            instance_id=instance_id, workflow_component=workflow_component
        )

        try:
            _, call = self.retry_policy.run_rpc(self._stub.ResumeWorkflowBeta1.with_call, req)

            return DaprResponse(headers=call.initial_metadata())
        except RpcError as err:
            raise DaprInternalError(err.details())

    def purge_workflow(self, instance_id: str, workflow_component: str) -> DaprResponse:
        """Purges a workflow.

            Args:
                instance_id (str): the ID of the workflow instance,
                                    e.g. `order_processing_workflow-103784`.
                workflow_component (str): the name of the workflow component
                                    that will run the workflow. e.g. `dapr`.

        Returns:
            :class:`DaprResponse` gRPC metadata returned from callee
        """
        # Warnings and input validation
        warn(
            'The Workflow API is a Beta version and is subject to change.',
            UserWarning,
            stacklevel=2,
        )
        validateNotBlankString(instance_id=instance_id, workflow_component=workflow_component)
        # Actual purge workflow invocation
        req = api_v1.PurgeWorkflowRequest(
            instance_id=instance_id, workflow_component=workflow_component
        )

        try:
            response, call = self.retry_policy.run_rpc(self._stub.PurgeWorkflowBeta1.with_call, req)

            return DaprResponse(headers=call.initial_metadata())

        except RpcError as err:
            raise DaprInternalError(err.details())

    def wait(self, timeout_s: float):
        """Waits for sidecar to be available within the timeout.

        It checks if sidecar socket is available within the given timeout.

        The example gets a secret from secret store:

            from dapr.clients import DaprClient

            with DaprClient() as d:
                d.wait(1) # waits for 1 second.
                # Sidecar is available after this.

        Args:
            timeout_s (float): timeout in seconds
        """
        warn(
            'The wait method is deprecated. A health check is now done automatically on client '
            'initialization.',
            DeprecationWarning,
            stacklevel=2,
        )
        start = time.time()
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout_s)
                try:
                    s.connect((self._uri.hostname, self._uri.port_as_int))
                    return
                except Exception as e:
                    remaining = (start + timeout_s) - time.time()
                    if remaining < 0:
                        raise e
                    time.sleep(min(1, remaining))

    # ---
    def get_metadata(self) -> GetMetadataResponse:
        """Returns information about the sidecar allowing for runtime
        discoverability.

        The metadata API returns a list of the components loaded,
        the activated actors (if present) and attributes with information
        attached.

        Each loaded component provides its name, type and version and also
        information about supported features in the form of component
        capabilities.
        """
        try:
            _resp, call = self.retry_policy.run_rpc(self._stub.GetMetadata.with_call, GrpcEmpty())
        except RpcError as err:
            raise DaprGrpcError(err) from err

        response: api_v1.GetMetadataResponse = _resp  # type alias
        # Convert to more pythonic formats
        active_actors_count = {
            type_count.type: type_count.count for type_count in response.active_actors_count
        }
        registered_components = [
            RegisteredComponents(
                name=i.name, type=i.type, version=i.version, capabilities=i.capabilities
            )
            for i in response.registered_components
        ]
        extended_metadata = dict(response.extended_metadata.items())

        return GetMetadataResponse(
            application_id=response.id,
            active_actors_count=active_actors_count,
            registered_components=registered_components,
            extended_metadata=extended_metadata,
            headers=call.initial_metadata(),
        )

    def set_metadata(self, attributeName: str, attributeValue: str) -> DaprResponse:
        """Adds a custom (extended) metadata attribute to the Dapr sidecar
        information stored by the Metadata endpoint.

        The metadata API allows you to store additional attribute information
        in the format of key-value pairs. These are ephemeral in-memory and
        are not persisted if a sidecar is reloaded. This information should
        be added at the time of a sidecar creation, for example, after the
        application has started.

        Args:
            attributeName (str): Custom attribute name. This is they key name
                                 in the key-value pair.
            attributeValue (str): Custom attribute value we want to store.
        """
        # input validation
        validateNotBlankString(attributeName=attributeName)
        # Type-checking should catch this but better safe at run-time than sorry.
        validateNotNone(attributeValue=attributeValue)
        # Actual invocation
        req = api_v1.SetMetadataRequest(key=attributeName, value=attributeValue)
        _, call = self.retry_policy.run_rpc(self._stub.SetMetadata.with_call, req)

        return DaprResponse(call.initial_metadata())

    def shutdown(self) -> DaprResponse:
        """Shutdown the sidecar.

        This will ask the sidecar to gracefully shutdown.

        The example shutdown the sidecar:

            from dapr.clients import DaprClient

            with DaprClient() as d:
                resp = d.shutdown()

        Returns:
            :class:`DaprResponse` gRPC metadata returned from callee
        """

        _, call = self.retry_policy.run_rpc(self._stub.Shutdown.with_call, GrpcEmpty())

        return DaprResponse(call.initial_metadata())
