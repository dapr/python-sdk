# -*- coding: utf-8 -*-

"""
Copyright 2025 The Dapr Authors
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

from dapr.clients.grpc._jobs import ConstantFailurePolicy, DropFailurePolicy, FailurePolicy, Job
from dapr.clients.grpc._request import BindingRequest, InvokeMethodRequest, JobEvent
from dapr.clients.grpc._response import InvokeMethodResponse, TopicEventResponse
from dapr.common.pubsub.subscription import SubscriptionMessage

# No cloudevents ImportError guard here: importing this subpackage imports the parent
# dapr.ext.grpc first, which already raises the actionable error.
from dapr.ext.grpc.aio.app import App, Rule  # type:ignore

__all__ = [
    'App',
    'Rule',
    'SubscriptionMessage',
    'InvokeMethodRequest',
    'InvokeMethodResponse',
    'BindingRequest',
    'TopicEventResponse',
    'Job',
    'JobEvent',
    'FailurePolicy',
    'DropFailurePolicy',
    'ConstantFailurePolicy',
]
