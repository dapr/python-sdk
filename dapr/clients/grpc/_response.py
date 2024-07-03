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

from __future__ import annotations

import contextlib
import json
import threading
from datetime import datetime
from enum import Enum
from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Text,
    Union,
    Sequence,
    TYPE_CHECKING,
    NamedTuple,
    Generator,
    TypeVar,
    Generic,
    Mapping,
)

from google.protobuf.any_pb2 import Any as GrpcAny
from google.protobuf.message import Message as GrpcMessage

from dapr.clients.base import DEFAULT_JSON_CONTENT_TYPE
from dapr.clients.grpc._helpers import (
    MetadataDict,
    MetadataTuple,
    to_bytes,
    to_str,
    tuple_to_dict,
    unpack,
    WorkflowRuntimeStatus,
)
from dapr.proto import api_service_v1, api_v1, appcallback_v1, common_v1

# Avoid circular import dependency by only importing DaprGrpcClient
# for type checking
if TYPE_CHECKING:
    from dapr.clients.grpc.client import DaprGrpcClient

TCryptoResponse = TypeVar(
    'TCryptoResponse', bound=Union[api_v1.EncryptResponse, api_v1.DecryptResponse]
)


class DaprResponse:
    """A base class for Dapr Response.

    This is the base class for Dapr Response. User can get the headers as a dict.

    Attributes:
        headers(dict): A dict to include the headers from Dapr gRPC Response.
    """

    def __init__(self, headers: MetadataTuple = ()):
        """Inits DapResponse with headers and trailers.

        Args:
            headers (tuple, optional): the tuple for the headers from response.
        """
        self.headers = headers  # type: ignore

    @property
    def headers(self) -> MetadataDict:
        """Gets headers as a dict."""
        return self.get_headers(as_dict=True)  # type: ignore

    @headers.setter
    def headers(self, val: MetadataTuple) -> None:
        """Sets response headers."""
        self._headers = val

    def get_headers(self, as_dict: bool = False) -> Union[MetadataDict, MetadataTuple]:
        """Gets headers from the response.

        Args:
            as_dict (bool): dict type headers if as_dict is True. Otherwise, return
                tuple headers.

        Returns:
            dict or tuple: response headers.
        """
        if as_dict:
            return tuple_to_dict(self._headers)
        return self._headers


class InvokeMethodResponse(DaprResponse):
    """The response of invoke_method API.

    This inherits from DaprResponse and has the helpers to handle bytes array
    and protocol buffer data.

    Attributes:
        headers (tuple, optional): the tuple for the headers from response.
        data (str, bytes, GrpcAny, GrpcMessage, optional): the serialized protocol
            buffer raw message
        content (bytes, optional): bytes data if response data is not serialized
            protocol buffer message
        content_type (str, optional): the type of `content`
        status_code (int, optional): the status code of the response
    """

    def __init__(
        self,
        data: Union[str, bytes, GrpcAny, GrpcMessage, None] = None,
        content_type: Optional[str] = None,
        headers: MetadataTuple = (),
        status_code: Optional[int] = None,
    ):
        """Initializes InvokeMethodReponse from :obj:`common_v1.InvokeResponse`.

        Args:
            data (str, bytes, GrpcAny, GrpcMessage, optional): the response data
                from Dapr response
            content_type (str, optional): the content type of the bytes data
            headers (tuple, optional): the headers from Dapr gRPC response
            status_code (int, optional): the status code of the response
        """
        super(InvokeMethodResponse, self).__init__(headers)
        self._content_type = content_type
        self.set_data(data)
        self._status_code = status_code

        # Set content_type to application/json type if content_type
        # is not given and date is bytes or str type.
        if not self.is_proto() and not content_type:
            self.content_type = DEFAULT_JSON_CONTENT_TYPE

    @property
    def proto(self) -> GrpcAny:
        """Gets raw serialized protocol buffer message.

        Raises:
            ValueError: data is not protocol buffer message object
        """
        return self._data

    def is_proto(self) -> bool:
        """Returns True if the response data is the serialized protocol buffer message."""
        return hasattr(self, '_data') and self._data.type_url != ''

    @property
    def data(self) -> bytes:
        """Gets raw bytes data if the response data content is not serialized
        protocol buffer message.

        Raises:
            ValueError: the response data is the serialized protocol buffer message
        """
        if self.is_proto():
            raise ValueError('data is protocol buffer message object.')
        return self._data.value

    @data.setter
    def data(self, val: Union[str, bytes]) -> None:
        """Sets str or bytes type data to request data."""
        self.set_data(val)

    def set_data(self, val: Union[str, bytes, GrpcAny, GrpcMessage, None]) -> None:
        """Sets data to request data."""
        if val is None:
            self._data = GrpcAny()
        elif isinstance(val, (bytes, str)):
            self._data = GrpcAny(value=to_bytes(val))
        elif isinstance(val, (GrpcAny, GrpcMessage)):
            self.pack(val)
        else:
            raise ValueError(f'invalid data type {type(val)}')

    def text(self) -> str:
        """Gets content as str if the response data content is not serialized
        protocol buffer message.

        Raises:
            ValueError: the response data is the serialized protocol buffer message
        """
        return to_str(self.data)

    def json(self) -> Dict[str, object]:
        """Gets the content as json if the response data content is not a serialized
        protocol buffer message.

        Returns:
            str: [description]
        """
        return json.loads(to_str(self.data))

    @property
    def content_type(self) -> Optional[str]:
        """Gets the content type of content attribute."""
        return self._content_type

    @content_type.setter
    def content_type(self, val: Optional[str]) -> None:
        """Sets content type for bytes data."""
        self._content_type = val

    def pack(self, val: Union[GrpcAny, GrpcMessage]) -> None:
        """Serializes protocol buffer message.

        Args:
            message (:class:`GrpcMessage`, :class:`GrpcAny`): the protocol buffer message object

        Raises:
            ValueError: message is neither GrpcAny nor GrpcMessage.
        """
        if isinstance(val, GrpcAny):
            self._data = val
        elif isinstance(val, GrpcMessage):
            self._data = GrpcAny()
            self._data.Pack(val)
        else:
            raise ValueError('invalid data type')

    @property
    def status_code(self) -> Optional[int]:
        """Gets the response status code attribute."""
        return self._status_code

    @status_code.setter
    def status_code(self, val: Optional[int]) -> None:
        """Sets the response status code."""
        self._status_code = val

    def unpack(self, message: GrpcMessage) -> None:
        """Deserializes the serialized protocol buffer message.

        Args:
            message (:class:`GrpcMessage`): the protocol buffer message object
                to which the response data is deserialized.

        Raises:
            ValueError: message is not protocol buffer message object or message's type is not
                matched with the response data type
        """

        if self.content_type is not None and self.content_type.lower() == 'application/x-protobuf':
            message.ParseFromString(self.data)
            return

        unpack(self.proto, message)


class BindingResponse(DaprResponse):
    """The response of invoke_binding API.

    This inherits from DaprResponse and has the helpers to handle bytes array data.

    Attributes:
        data (bytes): the data in response from the invoke_binding call
        binding_metadata (Dict[str, str]): metadata sent as a reponse by the binding
    """

    def __init__(
        self,
        data: Union[bytes, str],
        binding_metadata: Dict[str, str] = {},
        headers: MetadataTuple = (),
    ):
        """Initializes InvokeBindingReponse from :obj:`runtime_v1.InvokeBindingResponse`.

        Args:
            data (bytes): the data in response from the invoke_binding call
            binding_metadata (Dict[str, str]): metadata sent as a reponse by the binding
            headers (Tuple, optional): the headers from Dapr gRPC response

        Raises:
            ValueError: if the response data is not :class:`google.protobuf.any_pb2.Any`
                object.
        """
        super(BindingResponse, self).__init__(headers)
        self.data = data  # type: ignore
        self._metadata = binding_metadata

    def text(self) -> str:
        """Gets content as str."""
        return to_str(self._data)

    def json(self) -> Dict[str, object]:
        """Gets content as deserialized JSON dictionary."""
        return json.loads(to_str(self._data))

    @property
    def data(self) -> bytes:
        """Gets raw bytes data."""
        return self._data

    @data.setter
    def data(self, val: Union[bytes, str]) -> None:
        """Sets str or bytes type data to request data."""
        self._data = to_bytes(val)

    @property
    def binding_metadata(self) -> Dict[str, str]:
        """Gets the metadata in the response."""
        return self._metadata


class GetSecretResponse(DaprResponse):
    """The response of get_secret API.

    This inherits from DaprResponse

    Attributes:
        secret (Dict[str, str]): secret received from response
    """

    def __init__(self, secret: Dict[str, str], headers: MetadataTuple = ()):
        """Initializes GetSecretReponse from :obj:`dapr_v1.GetSecretResponse`.

        Args:
            secret (Dict[Str, str]): the secret from Dapr response
            headers (Tuple, optional): the headers from Dapr gRPC response
        """
        super(GetSecretResponse, self).__init__(headers)
        self._secret = secret

    @property
    def secret(self) -> Dict[str, str]:
        """Gets secret as a dict."""
        return self._secret


class GetBulkSecretResponse(DaprResponse):
    """The response of get_bulk_secret API.

    This inherits from DaprResponse

    Attributes:
        secret (Dict[str, Dict[str, str]]): secret received from response
    """

    def __init__(self, secrets: Dict[str, Dict[str, str]], headers: MetadataTuple = ()):
        """Initializes GetBulkSecretReponse from :obj:`dapr_v1.GetBulkSecretResponse`.

        Args:
            secrets (Dict[Str, Dict[str, str]]): the secret from Dapr response
            headers (Tuple, optional): the headers from Dapr gRPC response
        """
        super(GetBulkSecretResponse, self).__init__(headers)
        self._secrets = secrets

    @property
    def secrets(self) -> Dict[str, Dict[str, str]]:
        """Gets secrets as a dict."""
        return self._secrets


class StateResponse(DaprResponse):
    """The response of get_state API.

    This inherits from DaprResponse

    Attributes:
        data (bytes): the data in response from the get_state call
        etag (str): state's etag.
        headers (Tuple, optional): the headers from Dapr gRPC response
    """

    def __init__(self, data: Union[bytes, str], etag: str = '', headers: MetadataTuple = ()):
        """Initializes StateResponse from :obj:`runtime_v1.GetStateResponse`.

        Args:
            data (bytes): the data in response from the get_state call
            etag (str): state's etag.
            headers (Tuple, optional): the headers from Dapr gRPC response

        Raises:
            ValueError: if the response data is not :class:`google.protobuf.any_pb2.Any`
                object.
        """
        super(StateResponse, self).__init__(headers)
        self.data = data  # type: ignore
        self._etag = etag

    def text(self) -> str:
        """Gets content as str."""
        return to_str(self._data)

    def json(self) -> Dict[str, object]:
        """Gets content as deserialized JSON dictionary."""
        return json.loads(to_str(self._data))

    @property
    def etag(self) -> str:
        """Gets etag."""
        return self._etag

    @property
    def data(self) -> bytes:
        """Gets raw bytes data."""
        return self._data

    @data.setter
    def data(self, val: Union[bytes, str]) -> None:
        """Sets str or bytes type data to request data."""
        self._data = to_bytes(val)


class BulkStateItem:
    """A state item from bulk_get_state API.

    Attributes:
        key (str): state's key.
        data (Union[bytes, str]): state's data.
        etag (str): state's etag.
        error (str): error when state was retrieved
    """

    def __init__(self, key: str, data: Union[bytes, str], etag: str = '', error: str = ''):
        """Initializes BulkStateItem item from :obj:`runtime_v1.BulkStateItem`.

        Args:
            key (str): state's key.
            data (Union[bytes, str]): state's data.
            etag (str): state's etag.
            error (str): error when state was retrieved
        """
        self._key = key
        self._data = data  # type: ignore
        self._etag = etag
        self._error = error

    def text(self) -> str:
        """Gets content as str."""
        return to_str(self._data)

    def json(self) -> Dict[str, object]:
        """Gets content as deserialized JSON dictionary."""
        return json.loads(to_str(self._data))

    @property
    def key(self) -> str:
        """Gets key."""
        return self._key

    @property
    def data(self) -> Union[bytes, str]:
        """Gets raw data."""
        return self._data

    @property
    def etag(self) -> str:
        """Gets etag."""
        return self._etag

    @property
    def error(self) -> str:
        """Gets error."""
        return self._error


class BulkStatesResponse(DaprResponse):
    """The response of bulk_get_state API.

    This inherits from DaprResponse

    Attributes:
        data (Union[bytes, str]): state's data.
    """

    def __init__(self, items: Sequence[BulkStateItem], headers: MetadataTuple = ()):
        """Initializes BulkStatesResponse from :obj:`runtime_v1.GetBulkStateResponse`.

        Args:
            items (Sequence[BulkStatesItem]): the items retrieved.
            headers (Tuple, optional): the headers from Dapr gRPC response.
        """
        super(BulkStatesResponse, self).__init__(headers)
        self._items = items

    @property
    def items(self) -> Sequence[BulkStateItem]:
        """Gets the items."""
        return self._items


class QueryResponseItem:
    """A query response item from state store query API.

    Attributes:
        key (str): query reponse item's key.
        value (bytes): query reponse item's data.
        etag (str): query reponse item's etag.
        error (str): error when state was retrieved
    """

    def __init__(self, key: str, value: bytes, etag: str = '', error: str = ''):
        """Initializes QueryResponseItem item from :obj:`runtime_v1.QueryStateItem`.

        Args:
            key (str): query response item's key.
            value (bytes): query response item's data.
            etag (str): query response item's etag.
            error (str): error when state was retrieved
        """
        self._key = key
        self._value = value
        self._etag = etag
        self._error = error

    def text(self) -> str:
        """Gets value as str."""
        return to_str(self._value)

    def json(self) -> Dict[str, object]:
        """Gets value as deserialized JSON dictionary."""
        return json.loads(to_str(self._value))

    @property
    def key(self) -> str:
        """Gets key."""
        return self._key

    @property
    def value(self) -> bytes:
        """Gets raw value."""
        return self._value

    @property
    def etag(self) -> str:
        """Gets etag."""
        return self._etag

    @property
    def error(self) -> str:
        """Gets error."""
        return self._error


class QueryResponse(DaprResponse):
    """The response of state store query API.

    This inherits from DaprResponse

    Attributes:
        results (Sequence[QueryResponseItem]): the query results.
        token (str): query response token for pagination.
        metadata (Dict[str, str]): query response metadata.
    """

    def __init__(
        self,
        results: Sequence[QueryResponseItem],
        token: str = '',
        metadata: Dict[str, str] = dict(),
        headers: MetadataTuple = (),
    ):
        """Initializes QueryResponse from :obj:`runtime_v1.QueryStateResponse`.

        Args:
            results (Sequence[QueryResponseItem]): the query results.
            token (str): query response token for pagination.
            metadata (Dict[str, str]): query response metadata.
            headers (Tuple, optional): the headers from Dapr gRPC response.
        """
        super(QueryResponse, self).__init__(headers)
        self._metadata = metadata
        self._results = results
        self._token = token

    @property
    def results(self) -> Sequence[QueryResponseItem]:
        """Gets the query results."""
        return self._results

    @property
    def token(self) -> str:
        """Gets the query pagination token."""
        return self._token

    @property
    def metadata(self) -> Dict[str, str]:
        """Gets the query response metadata."""
        return self._metadata


class ConfigurationItem:
    """A config item from get_configuration API.

    Attributes:
        value (Union[bytes, str]): config's value.
        version (str): config's version.
        metadata (str): metadata
    """

    def __init__(self, value: str, version: str, metadata: Optional[Dict[str, str]] = dict()):
        """Initializes ConfigurationItem item from :obj:`runtime_v1.ConfigurationItem`.

        Args:
            value (str): config's value.
            version (str): config's version.
            metadata (Optional[Dict[str, str]] = dict()): metadata
        """
        self._value = value
        self._version = version
        self._metadata = metadata

    def text(self) -> str:
        """Gets content as str."""
        return to_str(self._value)

    def json(self) -> Dict[str, object]:
        """Gets content as deserialized JSON dictionary."""
        return json.loads(to_str(self._value))

    @property
    def value(self) -> str:
        """Gets value."""
        return self._value

    @property
    def version(self) -> str:
        """Gets version."""
        return self._version

    @property
    def metadata(self) -> Optional[Dict[str, str]]:
        """Gets metadata."""
        return self._metadata


class ConfigurationResponse(DaprResponse):
    """The response of get_configuration API.

    This inherits from DaprResponse

    Attributes:
        - items (Mapping[Text, ConfigurationItem]): state's data.
    """

    def __init__(
        self, items: Mapping[Text, common_v1.ConfigurationItem], headers: MetadataTuple = ()
    ):
        """Initializes ConfigurationResponse from :obj:`runtime_v1.GetConfigurationResponse`.

        Args:
            items (Mapping[str, common_v1.ConfigurationItem]): the items retrieved.
            headers (Tuple, optional): the headers from Dapr gRPC response.
        """
        super(ConfigurationResponse, self).__init__(headers)
        self._items: Dict[Text, ConfigurationItem] = dict()
        k: Text
        v: common_v1.ConfigurationItem
        for k, v in items.items():
            self._items[k] = ConfigurationItem(v.value, v.version, dict(v.metadata))

    @property
    def items(self) -> Dict[Text, ConfigurationItem]:
        """Gets the items."""
        return self._items


class ConfigurationWatcher:
    def __init__(self):
        self.store_name = None
        self.keys = None
        self.event: threading.Event = threading.Event()
        self.id: str = ''

    def watch_configuration(
        self,
        stub: api_service_v1.DaprStub,
        store_name: str,
        keys: List[str],
        handler: Callable[[Text, ConfigurationResponse], None],
        config_metadata: Optional[Dict[str, str]] = dict(),
    ):
        req = api_v1.SubscribeConfigurationRequest(
            store_name=store_name, keys=keys, metadata=config_metadata
        )
        thread = threading.Thread(target=self._read_subscribe_config, args=(stub, req, handler))
        thread.daemon = True
        thread.start()
        self.keys = keys
        self.store_name = store_name
        check = self.event.wait(timeout=5)
        if not check:
            print(f'Unable to get configuration id for keys {self.keys}')
            return None
        return self.id

    def _read_subscribe_config(
        self,
        stub: api_service_v1.DaprStub,
        req: api_v1.SubscribeConfigurationRequest,
        handler: Callable[[Text, ConfigurationResponse], None],
    ):
        try:
            responses: List[
                api_v1.SubscribeConfigurationResponse
            ] = stub.SubscribeConfigurationAlpha1(req)
            isFirst = True
            for response in responses:
                if isFirst:
                    self.id = response.id
                    self.event.set()
                    isFirst = False
                if len(response.items) > 0:
                    handler(response.id, ConfigurationResponse(response.items))
        except Exception:
            print(f'{self.store_name} configuration watcher for keys ' f'{self.keys} stopped.')
            pass


class TopicEventResponseStatus(Enum):
    # success is the default behavior: message is acknowledged and not retried
    success = appcallback_v1.TopicEventResponse.TopicEventResponseStatus.SUCCESS
    retry = appcallback_v1.TopicEventResponse.TopicEventResponseStatus.RETRY
    drop = appcallback_v1.TopicEventResponse.TopicEventResponseStatus.DROP


class TopicEventResponse(DaprResponse):
    """The response of subscribed topic events.

    This inherits from DaprResponse

    Attributes:
        status (Union[str, TopicEventResponseStatus]): status of the response
    """

    def __init__(
        self,
        status: Union[str, TopicEventResponseStatus],
        headers: MetadataTuple = (),
    ):
        """Initializes a TopicEventResponse.

        Args:
            status (TopicEventResponseStatus): The status of the response.
            headers (Tuple, optional): the headers from Dapr gRPC response.
        """
        super(TopicEventResponse, self).__init__(headers)
        values = [e.name for e in TopicEventResponseStatus]
        errormsg = f'`status` must be one of {values} or a TopicEventResponseStatus'

        if isinstance(status, str):
            try:
                status = TopicEventResponseStatus[status.lower()]
            except KeyError as e:
                raise KeyError(errormsg) from e
        if not isinstance(status, TopicEventResponseStatus):
            raise ValueError(errormsg)
        self._status = status

    @property
    def status(self) -> TopicEventResponseStatus:
        """Gets the status."""
        return self._status


class UnlockResponseStatus(Enum):
    success = api_v1.UnlockResponse.Status.SUCCESS
    """The Unlock operation for the referred lock was successful."""

    lock_does_not_exist = api_v1.UnlockResponse.Status.LOCK_DOES_NOT_EXIST
    """'The unlock operation failed: the referred lock does not exist."""

    lock_belongs_to_others = api_v1.UnlockResponse.Status.LOCK_BELONGS_TO_OTHERS
    """The unlock operation failed: the referred lock belongs to another owner."""

    internal_error = api_v1.UnlockResponse.Status.INTERNAL_ERROR
    """An internal error happened while handling the Unlock operation"""


class UnlockResponse(DaprResponse):
    """The response of an unlock operation.

    This inherits from DaprResponse

    Attributes:
        status (UnlockResponseStatus): the status of the unlock operation.
    """

    def __init__(
        self,
        status: UnlockResponseStatus,
        headers: MetadataTuple = (),
    ):
        """Initializes a UnlockResponse.

        Args:
            status (UnlockResponseStatus): The status of the response.
            headers (Tuple, optional): the headers from Dapr gRPC response.
        """
        super().__init__(headers)
        self._status = status

    @property
    def status(self) -> UnlockResponseStatus:
        """Gets the status."""
        return self._status


class TryLockResponse(contextlib.AbstractContextManager, DaprResponse):
    """The response of a try_lock operation.

    This inherits from DaprResponse and AbstractContextManager.

    Attributes:
        success (bool): the result of the try_lock operation.
    """

    def __init__(
        self,
        success: bool,
        client: DaprGrpcClient,
        store_name: str,
        resource_id: str,
        lock_owner: str,
        headers: MetadataTuple = (),
    ):
        """Initializes a TryLockResponse.

        Args:
            success (bool): the result of the try_lock operation.
            client (DaprClient): a reference to the dapr client used for the TryLock request.
            store_name (str): the lock store name used in the TryLock request.
            resource_id (str): the lock key or identifier used in the TryLock request.
            lock_owner (str):  the lock owner identifier used in the TryLock request.
            headers (Tuple, optional): the headers from Dapr gRPC response.
        """
        super().__init__(headers)
        self._success = success
        self._client = client
        self._store_name = store_name
        self._resource_id = resource_id
        self._lock_owner = lock_owner

    def __bool__(self) -> bool:
        return self._success

    @property
    def success(self) -> bool:
        """Gets the response success status."""
        return self._success

    def __exit__(self, *exc) -> None:
        """'Automatically unlocks the lock if this TryLockResponse was used as
        a ContextManager / `with` statement.

        Notice: we are not checking the result of the unlock operation.
        If this is something  you care about it might be wiser creating
        your own ContextManager that logs or otherwise raises exceptions
        if unlock doesn't return `UnlockResponseStatus.success`.
        """
        if self._success:
            self._client.unlock(self._store_name, self._resource_id, self._lock_owner)
        # else: there is no point unlocking a lock we did not acquire.

    async def __aexit__(self, *exc) -> None:
        """'Automatically unlocks the lock if this TryLockResponse was used as
        a ContextManager / `with` statement.

        Notice: we are not checking the result of the unlock operation.
        If this is something  you care about it might be wiser creating
        your own ContextManager that logs or otherwise raises exceptions
        if unlock doesn't return `UnlockResponseStatus.success`.
        """
        if self._success:
            await self._client.unlock(
                self._store_name,  # type: ignore
                self._resource_id,
                self._lock_owner,
            )
        # else: there is no point unlocking a lock we did not acquire.

    async def __aenter__(self) -> 'TryLockResponse':
        """Returns self as the context manager object."""
        return self


class GetMetadataResponse(DaprResponse):
    """GetMetadataResponse is a message that is returned on GetMetadata rpc call."""

    def __init__(
        self,
        application_id: str,
        active_actors_count: Dict[str, int],
        registered_components: Sequence[RegisteredComponents],
        extended_metadata: Dict[str, str],
        headers: MetadataTuple = (),
    ):
        """Initializes GetMetadataResponse.

        Args:
            application_id (str): The Application ID.
            active_actors_count (Dict[str, int]): mapping from the type of
                    registered actors to their number of running instances.
            registered_components (Sequence[RegisteredComponents]): list of
                    loaded components metadata.
            extended_metadata (Dict[str, str]): mapping of custom (extended)
                    attributes to their respective values.
            headers (Tuple, optional): the headers from Dapr gRPC response.
        """
        super().__init__(headers)
        self._application_id = application_id
        self._active_actors_count = active_actors_count
        self._registered_components = registered_components
        self._extended_metadata = extended_metadata

    @property
    def application_id(self) -> str:
        """The Application ID."""
        return self._application_id

    @property
    def active_actors_count(self) -> Dict[str, int]:
        """Mapping from the type of registered actors to their number of running instances."""
        return self._active_actors_count

    @property
    def registered_components(self) -> Sequence[RegisteredComponents]:
        """List of loaded components metadata."""
        return self._registered_components

    @property
    def extended_metadata(self) -> Dict[str, str]:
        """Mapping of custom (extended) attributes to their respective values."""
        return self._extended_metadata


class GetWorkflowResponse:
    """The response of get_workflow operation."""

    def __init__(
        self,
        instance_id: str,
        workflow_name: str,
        created_at: datetime,
        last_updated_at: str,
        runtime_status: WorkflowRuntimeStatus,
        properties: Dict[str, str] = {},
    ):
        """Initializes a GetWorkflowResponse.

        Args:
            instance_id (str): the instance ID assocated with this response.
            workflow_name (str): the name of the workflow that was started.
            created_at (datetime): the time at which the workflow started executing.
            last_updated_at (datetime): the time at which the workflow was last updated.
            runtime_status (WorkflowRuntimeStatus): the current runtime status of the workflow.
            properties (Dict[str, str]): properties sent as a reponse by the workflow.
        """
        self.instance_id = instance_id
        self.workflow_name = workflow_name
        self.created_at = created_at
        self.last_updated_at = last_updated_at
        self.runtime_status = runtime_status
        self.properties = properties


class StartWorkflowResponse:
    """The response of start_workflow operation."""

    def __init__(
        self,
        instance_id: str,
    ):
        """Initializes a StartWorkflowResponse.

        Args:
            instance_id (str): the instance ID assocated with this response.
        """
        self.instance_id = instance_id


class RegisteredComponents(NamedTuple):
    """Describes a loaded Dapr component."""

    name: str
    """Name of the component."""

    type: str
    """Component type."""

    version: str
    """Component version."""

    capabilities: Sequence[str]
    """Supported capabilities for this component type and version."""


class CryptoResponse(DaprResponse, Generic[TCryptoResponse]):
    """An iterable of cryptography API responses."""

    def __init__(self, stream: Generator[TCryptoResponse, None, None]):
        """Initialize a CryptoResponse.

        Args:
            stream (Generator[TCryptoResponse, None, None]): A stream of cryptography API responses.
        """
        self._stream = stream
        self._buffer = bytearray()
        self._expected_seq = 0

    def __iter__(self) -> Generator[bytes, None, None]:
        """Read the next chunk of data from the stream.

        Yields:
            bytes: The payload data of the next chunk from the stream.

        Raises:
            ValueError: If the sequence number of the next chunk is incorrect.
        """
        for chunk in self._stream:
            if chunk.payload.seq != self._expected_seq:
                raise ValueError('invalid sequence number in chunk')
            self._expected_seq += 1
            yield chunk.payload.data

    def read(self, size: int = -1) -> bytes:
        """Read bytes from the stream.

        If size is -1, the entire stream is read and returned as bytes.
        Otherwise, up to `size` bytes are read from the stream and returned.
        If the stream ends before `size` bytes are available, the remaining
        bytes are returned.

        Args:
            size (int): The maximum number of bytes to read. If -1 (the default),
                read until the end of the stream.

        Returns:
            bytes: The bytes read from the stream.
        """
        if size == -1:
            # Read the entire stream
            return b''.join(self)

        # Read the requested number of bytes
        data = bytes(self._buffer)
        self._buffer.clear()

        for chunk in self:
            data += chunk
            if len(data) >= size:
                break

        # Update the buffer
        remaining = data[size:]
        self._buffer.extend(remaining)

        # Return the requested number of bytes
        return data[:size]


class EncryptResponse(CryptoResponse[TCryptoResponse]):
    ...


class DecryptResponse(CryptoResponse[TCryptoResponse]):
    ...
