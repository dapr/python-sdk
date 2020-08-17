# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

import grpc  # type: ignore
from dapr.clients.grpc._state import StateOptions

from typing import Dict, Optional, Union

from google.protobuf.message import Message as GrpcMessage

from dapr.conf import settings
from dapr.proto import api_v1, api_service_v1, common_v1

from dapr.clients.grpc._helpers import MetadataTuple, DaprClientInterceptor, to_bytes
from dapr.clients.grpc._request import InvokeServiceRequest, BindingRequest
from dapr.clients.grpc._response import (
    BindingResponse,
    DaprResponse,
    GetSecretResponse,
    InvokeServiceResponse,
    StateResponse
)


class DaprClient:
    """The convenient layer implementation of Dapr gRPC APIs.

    This provides the wrappers and helpers to allows developers to use Dapr runtime gRPC API
    easily and consistently.

    Examples:

        >>> from dapr.clients import DaprClient
        >>> d = DaprClient()
        >>> resp = d.invoke_service('callee', 'method', b'data')

    With context manager:

        >>> from dapr.clients import DaprClient
        >>> with DaprClient() as d:
        ...     resp = d.invoke_service('callee', 'method', b'data')
    """

    def __init__(self, address: Optional[str] = None):
        """Connects to Dapr Runtime and initialize gRPC client stub.

        Args:
            address (str, optional): Dapr Runtime gRPC endpoint address.
        """
        if not address:
            address = f"{settings.DAPR_RUNTIME_HOST}:{settings.DAPR_GRPC_PORT}"
        self._channel = grpc.insecure_channel(address)   # type: ignore

        if settings.DAPR_API_TOKEN:
            api_token_interceptor = DaprClientInterceptor([
                ('dapr-api-token', settings.DAPR_API_TOKEN), ])
            self._channel = grpc.intercept_channel(   # type: ignore
                self._channel, api_token_interceptor)

        self._stub = api_service_v1.DaprStub(self._channel)

    def close(self):
        """Closes Dapr runtime gRPC channel."""
        self._channel.close()

    def __del__(self):
        self.close()

    def __enter__(self) -> 'DaprClient':
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

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
            id: str,
            method: str,
            data: Union[bytes, str, GrpcMessage],
            content_type: Optional[str] = None,
            metadata: Optional[MetadataTuple] = None,
            http_verb: Optional[str] = None,
            http_querystring: Optional[MetadataTuple] = None) -> InvokeServiceResponse:
        """Invokes the target service to call method.

        This can invoke the specified target service to call method with bytes array data or
        custom protocol buffer message. If your callee application uses http appcallback,
        http_verb and http_querystring must be specified. Otherwise, Dapr runtime will return
        error.

        The example calls `callee` service with bytes data, which implements grpc appcallback:

            from dapr.clients import DaprClient

            with DaprClient() as d:
                resp = d.invoke_service(
                    id='callee',
                    method='method',
                    data=b'message',
                    content_type='text/plain',
                    metadata=(
                        ('header1', 'value1')
                    ),
                )

                # resp.content includes the content in bytes.
                # resp.content_type specifies the content type of resp.content.
                # Thus, resp.content can be deserialized properly.

        When sending custom protocol buffer message object, it doesn't requires content_type:

            from dapr.clients import DaprClient

            req_data = dapr_example_v1.CustomRequestMessage(data='custom')

            with DaprClient() as d:
                resp = d.invoke_service(
                    id='callee',
                    method='method',
                    data=req_data,
                    metadata=(
                        ('header1', 'value1')
                    ),
                )
                # Create protocol buffer object
                resp_data = dapr_example_v1.CustomResponseMessage()
                # Deserialize to resp_data
                resp.unpack(resp_data)

        The example calls `callee` service which implements http appcallback:

            from dapr.clients import DaprClient

            with DaprClient() as d:
                resp = d.invoke_service(
                    id='callee',
                    method='method',
                    data=b'message',
                    content_type='text/plain',
                    metadata=(
                        ('header1', 'value1')
                    ),
                    http_verb='POST',
                    http_querystring=(
                        ('key1', 'value1')
                    ),
                )

                # resp.content includes the content in bytes.
                # resp.content_type specifies the content type of resp.content.
                # Thus, resp.content can be deserialized properly.

        Args:
            id (str): the callee app id
            method (str): the method name which is called
            data (bytes or :obj:`google.protobuf.message.Message`): bytes or Message for data
                which will send to id
            metadata (tuple, optional): custom metadata
            http_verb (str, optional): http method verb to call HTTP callee application
            http_querystring (tuple, optional): the tuple to represent query string

        Returns:
            :class:`InvokeServiceResponse` object returned from callee
        """
        req_data = InvokeServiceRequest(data, content_type)
        http_ext = None
        if http_verb:
            http_ext = self._get_http_extension(http_verb, http_querystring)

        req = api_v1.InvokeServiceRequest(
            id=id,
            message=common_v1.InvokeRequest(
                method=method,
                data=req_data.proto,
                content_type=req_data.content_type,
                http_extension=http_ext)
        )

        response, call = self._stub.InvokeService.with_call(req, metadata=metadata)

        resp_data = InvokeServiceResponse(response.data, response.content_type)
        resp_data.headers = call.initial_metadata()  # type: ignore
        return resp_data

    def invoke_binding(
            self,
            name: str,
            operation: str,
            data: Union[bytes, str],
            binding_metadata: Dict[str, str] = {},
            metadata: Optional[MetadataTuple] = ()) -> BindingResponse:
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
                    name = 'kafkaBinding',
                    operation = 'create',
                    data = b'message',
                    metadata = (
                        ('header1', 'value1)
                    ),
                )
                # resp.data includes the response data in bytes.
                # resp.metadata include the metadata returned from the external system.

        Args:
            name (str): the name of the binding as defined in the components
            operation (str): the operation to perform on the binding
            data (bytes or str): bytes or str for data which will sent to the binding
            binding_metadata (dict, optional): metadata for output binding
            metadata (tuple, optional): custom metadata to send to the binding

        Returns:
            :class:`InvokeBindingResponse` object returned from binding
        """
        req_data = BindingRequest(data, binding_metadata)

        req = api_v1.InvokeBindingRequest(
            name=name,
            data=req_data.data,
            metadata=req_data.binding_metadata,
            operation=operation
        )

        response, call = self._stub.InvokeBinding.with_call(req, metadata=metadata)
        return BindingResponse(
            response.data, dict(response.metadata),
            call.initial_metadata())

    def publish_event(
            self,
            pubsub_name: str,
            topic: str,
            data: Union[bytes, str],
            metadata: Optional[MetadataTuple] = ()) -> DaprResponse:
        """Publish to a given topic.
        This publishes an event with bytes array or str data to a specified topic and
        specified pubsub component. The str data is encoded into bytes with default
        charset of utf-8. Custom metadata can be passed with the metadata field which
        will be passed on a gRPC metadata.

        The example publishes a byte array event to a topic:

            from dapr.clients import DaprClient
            with DaprClient() as d:
                resp = d.publish_event(
                    pubsub_name='pubsub_1'
                    topic='TOPIC_A'
                    data=b'message',
                    metadata=(
                        ('header1', 'value1')
                    ),
                )
                # resp.headers includes the gRPC initial metadata.

        Args:
            pubsub_name (str): the name of the pubsub component
            topic (str): the topic name to publish to
            data (bytes or str): bytes or str for data
            metadata (tuple, optional): custom metadata

        Returns:
            :class:`DaprResponse` gRPC metadata returned from callee
        """
        if not isinstance(data, bytes) and not isinstance(data, str):
            raise ValueError(f'invalid type for data {type(data)}')

        req_data = data
        if isinstance(data, str):
            req_data = data.encode('utf-8')

        req = api_v1.PublishEventRequest(
            pubsub_name=pubsub_name,
            topic=topic,
            data=req_data)

        # response is google.protobuf.Empty
        _, call = self._stub.PublishEvent.with_call(req, metadata=metadata)

        return DaprResponse(call.initial_metadata())

    def get_state(
            self,
            store_name: str,
            key: str,
            metadata: Optional[MetadataTuple] = ()) -> DaprResponse:
        """Gets value from a statestore with a key

        The example gets value from a statestore:
            from dapr import DaprClient
            with DaprClient() as d:
                resp = d.get_state(
                    store_name='state_store'
                    key='key_1',
                    metadata=(
                        ('header1', 'value1')
                    ),
                )

        Args:
            store_name (str): the state store name to get from
            key (str): the key of the key-value pair to be gotten
            metadata (tuple, optional): custom metadata

        Returns:
            :class:`StateResponse` gRPC metadata returned from callee
            and value obtained from the state store
        """

        if len(store_name) == 0 or len(store_name.strip()) == 0:
            raise ValueError("State store name cannot be empty")
        req = api_v1.GetStateRequest(store_name=store_name, key=key)
        response, call = self._stub.GetState.with_call(req, metadata=metadata)
        return StateResponse(
            data=response.data,
            headers=call.initial_metadata())

    def save_state(
            self,
            store_name: str,
            key: str,
            value: Union[bytes, str],
            etag: Optional[str] = None,
            options: Optional[StateOptions] = None,
            metadata: Optional[MetadataTuple] = ()) -> DaprResponse:
        """Saves key-value pairs to a statestore

        This saves a value to the statestore with a given key and state store name.
        Options for request can be passed with the options field and custom
        metadata can be passed with metadata field.

        The example saves states to a statestore:
            from dapr import DaprClient
            with DaprClient() as d:
                resp = d.save_state(
                    store_name='state_store'
                    states=[{'key': 'key1', 'value': 'value1'}],
                    etag='etag',
                    metadata=(
                        ('header1', 'value1')
                    ),
                )

        Args:
            store_name (str): the state store name to save to
            key (str): the key to be saved
            value (bytes or str): the value to be saved
            etag (str, optional): the etag to save with
            options (StateOptions, optional): custom options
                for concurrency and consistency
            metadata (tuple, optional): custom metadata

        Returns:
            :class:`DaprResponse` gRPC metadata returned from callee
        """
        if not isinstance(value, (bytes, str)):
            raise ValueError(f'invalid type for data {type(value)}')

        req_value = value

        if len(store_name) == 0 or len(store_name.strip()) == 0:
            raise ValueError("State store name cannot be empty")

        if options is None:
            state_options = None
        else:
            state_options = options.get_proto()

        state = common_v1.StateItem(
            key=key, value=to_bytes(req_value), etag=etag, options=state_options)

        req = api_v1.SaveStateRequest(store_name=store_name, states=[state])
        response, call = self._stub.SaveState.with_call(req, metadata=metadata)
        return DaprResponse(
            headers=call.initial_metadata())

    def delete_state(
            self,
            store_name: str,
            key: str,
            etag: Optional[str] = None,
            options: Optional[StateOptions] = None,
            metadata: Optional[MetadataTuple] = ()) -> DaprResponse:
        """Deletes key-value pairs from a statestore

        This deletes a value from the statestore with a given key and state store name.
        Options for request can be passed with the options field and custom
        metadata can be passed with metadata field.

        The example deletes states from a statestore:
            from dapr import DaprClient
            with DaprClient() as d:
                resp = d.delete_state(
                    store_name='state_store',
                    key='key1'
                    etag='etag',
                    metadata=(
                        ('header1', 'value1')
                    )
                )

        Args:
            store_name (str): the state store name to delete from
            key (str): the key of the key-value pair to delete
            etag (str, optional): the etag to delete with
            options (StateOptions, optional): custom options
                for concurrency and consistency
            metadata (tuple, optional): custom metadata

        Returns:
            :class:`DaprResponse` gRPC metadata returned from callee
        """

        if len(store_name) == 0 or len(store_name.strip()) == 0:
            raise ValueError("State store name cannot be empty")

        if options is None:
            state_options = None
        else:
            state_options = options.get_proto()

        req = api_v1.DeleteStateRequest(store_name=store_name, key=key,
                                        etag=etag, options=state_options)
        response, call = self._stub.DeleteState.with_call(req, metadata=metadata)
        return DaprResponse(
            headers=call.initial_metadata())

    def get_secret(
            self,
            store_name: str,
            key: str,
            secret_metadata: Optional[Dict[str, str]] = {},
            metadata: Optional[MetadataTuple] = ()) -> GetSecretResponse:
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
                    metadata=(
                        ('headerA', 'valueB')
                    ),
                )

                # resp.headers includes the gRPC initial metadata.
                # resp.trailers includes that gRPC trailing metadata.

        Args:
            store_name (str): store name to get secret from
            key (str): str for key
            secret_metadata (Dict[str, str], Optional): metadata of request
            metadata (MetadataTuple, optional): custom metadata

        Returns:
            :class:`GetSecretResponse` object with the secret and metadata returned from callee
        """

        req = api_v1.GetSecretRequest(
            store_name=store_name,
            key=key,
            metadata=secret_metadata)

        response, call = self._stub.GetSecret.with_call(req, metadata=metadata)

        return GetSecretResponse(
            secret=response.data,
            headers=call.initial_metadata())
