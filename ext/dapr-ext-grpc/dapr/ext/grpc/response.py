# -*- coding: utf-8 -*-

"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT License.
"""

from typing import List,  Optional, Tuple

from dapr.proto import common_v1, appcallback_v1


class InputBindingResponse:
    def __init__(
            self,
            state_store: Optional[str]=None,
            states: Optional[Tuple[Tuple[str, bytes], ...]]=(),
            bindings: Optional[List[str]]=[],
            binding_data: Optional[bytes]=None,
            binding_concurrnecy: Optional[str]='SEQUENTIAL'):
        self._resp = appcallback_v1.BindingEventResponse()

        if state_store is not None:
            state_items = []
            for key, val in states:
                if not isinstance(val, bytes):
                    raise ValueError(f'{val} is not bytes')
                state_items.append(common_v1.StateItem(key=key, value=val))
            self._resp.state_store = state_store
            self._resp.states = state_items

        if len(bindings) > 0:
            self._resp.to = bindings
            self._resp.data = binding_data
            self._resp.concurrency = \
                appcallback_v1.BindingEventResponse.BindingEventConcurrency.Value(binding_concurrnecy)

    @property
    def event_response(self) -> appcallback_v1.BindingEventResponse:
        return self._resp
