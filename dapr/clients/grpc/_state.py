from enum import Enum
from dapr.proto import common_v1
from typing import Optional
from dapr.clients.grpc._helpers import convert_string_to_duration


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


class RetryPattern(Enum):
    """Represents the retry pattern for a Dapr State Api Call"""
    unspecified = common_v1.StateRetryPolicy.RetryPattern.RETRY_UNSPECIFIED  # type: ignore
    linear = common_v1.StateRetryPolicy.RetryPattern.RETRY_LINEAR  # type: ignore
    exponential = common_v1.StateRetryPolicy.RetryPattern.RETRY_EXPONENTIAL  # type: ignore


class RetryPolicy:
    """Represents the policy for retrying Dapr State Api Calls
    Args:
        threshold (Consistency, optional)
    """

    def __init__(
            self,
            threshold: int,
            interval: str,
            pattern: Optional[RetryPattern] = RetryPattern.unspecified):
        self.threshold = threshold
        self.pattern = pattern.value  # type: ignore
        self.interval = interval


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
        retry_policy: Optional[RetryPolicy] = None
    ):
        self.consistency = consistency
        self.concurrency = concurrency
        self.retry_policy = self.__get_retry_policy(retry_policy)

    def get_proto(self):
        return common_v1.StateOptions(
            concurrency=self.concurrency.value,  # type: ignore
            consistency=self.consistency.value,  # type: ignore
            retry_policy=self.retry_policy
        )

    def __get_retry_policy(self, retry_policy: Optional[RetryPolicy]):
        if retry_policy is None:
            return None
        else:
            return common_v1.StateRetryPolicy(
                threshold=retry_policy.threshold,
                pattern=retry_policy.pattern,
                interval=convert_string_to_duration(retry_policy.interval)
            )
