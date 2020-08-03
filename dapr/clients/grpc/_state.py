from enum import Enum
from dapr.proto import common_v1


class State:
    def __init__(self, key, value, etag, options):
        self.key = key
        self.value = value
        self.etag = etag
        self.options = options


class Consistency(Enum):
    eventual = common_v1.StateOptions.StateConsistency.CONSISTENCY_EVENTUAL
    strong = common_v1.StateOptions.StateConsistency.CONSISTENCY_STRONG


class Concurrency(Enum):
    first_write = common_v1.StateOptions.StateConcurrency.CONCURRENCY_FIRST_WRITE
    last_write = common_v1.StateOptions.StateConcurrency.CONCURRENCY_LAST_WRITE


class RetryPolicy:
    def __init__(self, threshold, interval, pattern):
        self.threshold = threshold
        self.interval = interval
        if pattern is None:
            self.pattern = common_v1.StateRetryPolicy.RetryPattern.RETRY_UNSPECIFIED


class RetryPattern(Enum):
    linear = common_v1.StateRetryPolicy.RetryPattern.RETRY_LINEAR
    exponential = common_v1.StateRetryPolicy.RETRY_EXPONENTIAL


class StateOptions:
    def __init__(self, consistency: Consistency = None,
                 concurrency: Concurrency = None, retry_policy: RetryPolicy = None):
        if consistency is None:
            self.consistency = common_v1.StateOptions.StateConsistency.CONSISTENCY_UNSPECIFIED
        else:
            self.consistency = consistency.value
        if concurrency is None:
            self.concurrency = concurrency.value
