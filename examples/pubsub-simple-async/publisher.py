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


async def main() -> None:
    async with DaprClient() as client:
        for id in range(1, 4):
            req_data = {'id': id, 'message': 'hello world'}

            await client.publish_event(
                pubsub_name='pubsub',
                topic_name='TOPIC_A',
                data=json.dumps(req_data),
                data_content_type='application/json',
            )

            print(req_data, flush=True)
            await asyncio.sleep(0.5)

        # A second topic, handled by a second async handler on the same subscriber.
        req_data = {'id': 4, 'message': 'hello world'}
        await client.publish_event(
            pubsub_name='pubsub',
            topic_name='TOPIC_B',
            data=json.dumps(req_data),
            data_content_type='application/json',
        )
        print(req_data, flush=True)

        await asyncio.sleep(0.5)

        # Bulk publish multiple events at once using publish_events
        bulk_events = [
            json.dumps({'id': 20, 'message': 'bulk event 1'}),
            json.dumps({'id': 21, 'message': 'bulk event 2'}),
            json.dumps({'id': 22, 'message': 'bulk event 3'}),
        ]

        resp = await client.publish_events(
            pubsub_name='pubsub',
            topic_name='TOPIC_A',
            data=bulk_events,
            data_content_type='application/json',
        )

        print(
            f'Bulk published {len(bulk_events)} events. Failed entries: {len(resp.failed_entries)}',
            flush=True,
        )

        await asyncio.sleep(0.5)


asyncio.run(main())
