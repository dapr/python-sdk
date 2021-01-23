from enum import Enum
from dapr.proto import common_v1
from typing import Dict, Optional, Union


class Consistency(Enum):
    """Represents the consistency mode for a Dapr State Api Call"""
    unspecified = common_v1.StateOptions.StateConsistency.CONSISTENCY_UNSPECIFIED  # type: ignore
    eventual = common_v1.StateOptions.StateConsistency.CONSISTENCY_EVENTUAL  # type: ignore
    strong = common_v1.StateOptions.StateConsistency.CONSISTENCY_STRONG  # type: ignore


class Concurrency(Enum):
    """Represents the consistency mode for a Dapr State Api Call"""
    unspecified = common_v1.StateOptions.StateConcurrency.CONCURRENCY_UNSPECIFIED  # type: ignore
    first_write = common_v1.StateOptions.StateConcurrency.CONCURRENCY_FIRST_WRITE  # type: ignore
    last_write = common_v1.StateOptions.StateConcurrency.CONCURRENCY_LAST_WRITE  # type: ignore


class StateOptions:
    """Represents options for a Dapr State Api Call
    Args:
        consistency (Consistency, optional): the consistency mode
        concurrency (Concurrency, optional): the concurrency mode
        retry_policy (RetryPolicy, optional): the policy for retrying the api calls
    """

    def __init__(
        self,
        consistency: Optional[Consistency] = Consistency.unspecified,
        concurrency: Optional[Concurrency] = Concurrency.unspecified,
    ):
        self.consistency = consistency
        self.concurrency = concurrency

    def get_proto(self):
        return common_v1.StateOptions(
            concurrency=self.concurrency.value,  # type: ignore
            consistency=self.consistency.value,  # type: ignore
        )


class StateItem:
    """Represents a state for Dapr State Api Call
    Args:
        key (str): the key for the state
        value (Union[bytes, str]): value of the state
        etag (str, optional): the etag for the state
        options (StateOptions, optional): options for the state
        metadata (Dict[str, str], optional): metadata for the state
    """

    def __init__(
        self,
        key: str,
        value: Union[bytes, str],
        etag: Optional[str] = None,
        options: Optional[StateOptions] = None,
        metadata: Optional[Dict[str, str]] = dict()
    ):
        """Inits StateItem with the required parameters.

        Args:
            key (str): the key for the state
            value (Union[bytes, str]): value of the state
            etag (str, optional): the etag for the state
            options (StateOptions, optional): options for the state
            metadata (Dict[str, str], optional): metadata for the state

        Raises:
            ValueError: value is not bytes or str
        """
        if not isinstance(value, (bytes, str)):
            raise ValueError(f'invalid type for data {type(value)}')

        self._key = key
        self._value = value
        self._etag = etag
        self._options = options
        self._metadata = metadata

    @property
    def key(self):
        """Get key from :class:`StateItem`"""
        return self._key

    @property
    def value(self):
        """Get value from :class:`StateItem`"""
        return self._value

    @property
    def etag(self):
        """Get etag from :class:`StateItem`"""
        return self._etag

    @etag.setter
    def etag(self, val: Optional[str] = None):
        """Set etag for instance of :class:`StateItem`"""
        self._etag = val

    @property
    def metadata(self):
        """Get metadata from :class:`StateItem`"""
        return self._metadata

    @metadata.setter
    def metadata(self, meta: Dict[str, str]):
        """Set metadata for instance of :class:`StateItem`"""
        self._metadata = meta

    @property
    def options(self):
        """Get options from :class:`StateItem`"""
        return self._options

    @options.setter
    def options(self, op: StateOptions):
        """Set options for instance of :class:`StateItem`"""
        self._options = op
