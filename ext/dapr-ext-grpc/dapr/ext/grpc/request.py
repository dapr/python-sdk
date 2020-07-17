# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from typing import Dict, Optional


class InputBindingRequest:
    """A request data representation for invoke_service API.

    This stores the request data with the proper serialization. This seralizes
    data to :obj:`google.protobuf.any_pb2.Any` if data is the type of protocol
    buffer message.

    Attributes:
        data (:obj:`google.protobuf.any_pb2.Any`): the serialized data for
            invoke_service request.
    """

    def __init__(
            self,
            metadata: Dict[str, str] = {},
            data: Optional[bytes] = None):
        """Inits InvokeServiceRequestData with data and content_type.

        Args:
            data (bytes, str, or :obj:`google.protobuf.message.Message`): the data
                which is used for invoke_service request.
            content_type (str): the content_type of data when the data is bytes.
                The default content type is application/json.

        Raises:
            ValueError: data is not bytes or :obj:`google.protobuf.message.Message`.
        """
        self.data = data
        self.metadata = metadata

    @property
    def metadata(self) -> Dict[str, str]:
        """Returns headers tuple as a dict."""
        return self._metadata

    @metadata.setter
    def metadata(self, val: Dict[str, str]) -> None:
        if not isinstance(val, dict):
            raise ValueError(f'invalid data type {type(val)}')
        self._metadata = val

    @property
    def data(self) -> bytes:
        return self._data

    @data.setter
    def data(self, val: bytes) -> None:
        if not isinstance(val, bytes):
            raise ValueError(f'invalid data type {type(val)}')
        self._data = val

    @property
    def text(self) -> str:
        return self.data.decode('utf-8')
