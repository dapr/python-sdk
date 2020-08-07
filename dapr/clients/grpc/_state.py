from enum import Enum
from dapr.proto import common_v1
from typing import Optional


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
