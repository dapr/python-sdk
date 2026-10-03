# ------------------------------------------------------------
# Copyright 2025 The Dapr Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------

import asyncio

from dapr.ext.grpc.aio import App, InvokeMethodRequest, InvokeMethodResponse

app = App()


@app.method(name='my-method')
async def mymethod(request: InvokeMethodRequest) -> InvokeMethodResponse:
    print(request.metadata, flush=True)
    print(request.text(), flush=True)

    # Handlers are awaited on the server's event loop, so awaiting I/O here
    # (a database read, an outbound HTTP call) leaves the loop free to serve
    # other in-flight invocations instead of tying up a worker thread.
    await asyncio.sleep(0.5)

    return InvokeMethodResponse(b'INVOKE_RECEIVED', 'text/plain; charset=UTF-8')


asyncio.run(app.run(13551))
