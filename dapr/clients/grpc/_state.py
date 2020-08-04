from enum import Enum
from dapr.proto import common_v1


class State:
    def __init__(self, key, value, etag, options):
        self.key = key
        self.value = value
        self.etag = etag
        self.options = options


class Consistency(Enum):
    eventual = common_v1.StateOptions.StateConsistency.CONSISTENCY_EVENTUAL  # type: ignore
    strong = common_v1.StateOptions.StateConsistency.CONSISTENCY_STRONG  # type: ignore


class Concurrency(Enum):
    first_write = common_v1.StateOptions.StateConcurrency.CONCURRENCY_FIRST_WRITE  # type: ignore
    last_write = common_v1.StateOptions.StateConcurrency.CONCURRENCY_LAST_WRITE  # type: ignore


class StateOptions:
    def __init__(self, consistency=None,
                 concurrency=None, retry_policy=None):
        if consistency is None:
            self.consistency = \
                common_v1.StateOptions.StateConsistency.CONSISTENCY_UNSPECIFIED  # type: ignore
        else:
            self.consistency = consistency.value
        if concurrency is None:
            self.concurrency = \
                common_v1.StateOptions.StateConcurrency.CONCURRENCY_UNSPECIFIED  # type: ignore
        else:
            self.concurrency = concurrency.value
