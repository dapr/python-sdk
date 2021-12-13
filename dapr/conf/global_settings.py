# -*- coding: utf-8 -*-

"""
Copyright 2021 The Dapr Authors
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
DAPR_RUNTIME_HOST = '127.0.0.1'
DAPR_HTTP_PORT = 3500
DAPR_GRPC_PORT = 50001
DAPR_API_VERSION = 'v1.0'

DAPR_API_METHOD_INVOCATION_PROTOCOL = 'http'

DAPR_HTTP_TIMEOUT_SECONDS = 60
