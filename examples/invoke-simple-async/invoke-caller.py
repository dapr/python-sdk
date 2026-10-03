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
import json

from dapr.aio.clients import DaprClient


async def invoke_receiver(client: DaprClient, request_id: int) -> None:
    req_data = {'id': request_id, 'message': 'hello world'}

    resp = await client.invoke_method(
        'invoke-receiver',
        'my-method',
        data=json.dumps(req_data),
    )

    print(resp.content_type, flush=True)
    print(resp.text(), flush=True)


async def main() -> None:
    async with DaprClient() as client:
        # All three invocations are in flight at once. Each one sleeps for half a
        # second on the receiver, yet the whole gather finishes in about that same
        # half second because the async receiver interleaves them.
        await asyncio.gather(*(invoke_receiver(client, request_id) for request_id in (1, 2, 3)))


asyncio.run(main())
