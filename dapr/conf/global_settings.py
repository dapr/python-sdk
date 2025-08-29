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

# Default environment settings that environment variables overrides

HTTP_APP_PORT = 3000
GRPC_APP_PORT = 3010

DAPR_API_TOKEN = None
DAPR_HTTP_ENDPOINT = None
DAPR_GRPC_ENDPOINT = None
DAPR_RUNTIME_HOST = '127.0.0.1'
DAPR_HTTP_PORT = 3500
DAPR_GRPC_PORT = 50001
DAPR_API_VERSION = 'v1.0'
DAPR_HEALTH_TIMEOUT = 60  # seconds

DAPR_API_MAX_RETRIES = 0
DAPR_API_TIMEOUT_SECONDS = 60

DAPR_API_METHOD_INVOCATION_PROTOCOL = 'http'

DAPR_HTTP_TIMEOUT_SECONDS = 60

# gRPC keepalive (disabled by default; enable via env to help with idle debugging sessions)
DAPR_GRPC_KEEPALIVE_ENABLED: bool = False
DAPR_GRPC_KEEPALIVE_TIME_MS: int = 120000  # send keepalive pings every 120s
DAPR_GRPC_KEEPALIVE_TIMEOUT_MS: int = (
    20000  # wait 20s for ack before considering the connection dead
)
DAPR_GRPC_KEEPALIVE_PERMIT_WITHOUT_CALLS: bool = False  # allow pings when there are no active calls
