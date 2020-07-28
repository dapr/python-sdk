from enum import Enum
from dapr.proto import common_v1


class State:
    def __init__(self, key, value, etag, options: StateOptions = None):
        self.key = key
        self.value = value
        self.etag = etag
        self.options = options

class Consistency(Enum):
    EVENTUAL = common_v1.StateOptions.StateConsistency.CONSISTENCY_EVENTUAL
    STRONG = common_v1.StateOptions.StateConsistency.CONSISTENCY_STRONG

class Concurrency(Enum):
    FIRST_WRITE = common_v1.StateOptions.StateConcurrency.CONCURRENCY_FIRST_WRITE
    LAST_WRITE = common_v1.StateOptions.StateConcurrency.CONCURRENCY_LAST_WRITE

class RetryPolicy:
    def __init__(self, threshold, interval, pattern: RetryPattern):
        self.threshold = threshold
        self.interval = interval
        if pattern is None:
            self.pattern = common_v1.StateOptions.RetryPattern.RETRY_UNSPECIFIED

class RetryPattern(Enum):
    LINEAR = common_v1.StateOptions.StateRetryPolicy.RetryPattern.RETRY_LINEAR
    EXPONENTIAL = common_v1.StateOptions.StateRetryPolicy.RetryPattern.RETRY_EXPONENTIAL

class StateOptions:
    def __init__(self, consistency: Consistency=None, concurrency: Concurrency=None, retry_policy):
        if consistency is None:
            self.consistency = common_v1.StateOptions.StateConsistency.CONSISTENCY_UNSPECIFIED 
        else:
            self.consistency = consistency.value
        if concurrency is None:
            self.concurrency = concurrency.value
