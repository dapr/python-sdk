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

from dapr.ext.grpc.aio import App, SubscriptionMessage, TopicEventResponse

app = App()


@app.subscribe(pubsub_name='pubsub', topic='TOPIC_A')
async def mytopic(event: SubscriptionMessage) -> TopicEventResponse:
    # event.data() is already parsed based on the content type (dict for application/json)
    data = event.data()

    # Awaiting inside the handler yields the event loop, so the subscriber keeps
    # accepting deliveries while this one waits on I/O.
    await asyncio.sleep(0)

    print(
        f'Subscriber received: id={data["id"]}, message="{data["message"]}", '
        f'content_type="{event.data_content_type()}"',
        flush=True,
    )
    return TopicEventResponse('success')


@app.subscribe(pubsub_name='pubsub', topic='TOPIC_B')
async def myothertopic(event: SubscriptionMessage) -> TopicEventResponse:
    data = event.data()

    await asyncio.sleep(0)

    print(
        f'Other-Subscriber received: id={data["id"]}, message="{data["message"]}", '
        f'content_type="{event.data_content_type()}"',
        flush=True,
    )
    return TopicEventResponse('success')


async def healthy() -> None:
    # Awaited by the app health check. Deliberately silent: daprd probes on a timer, so
    # printing here would bury the subscriber output this example exists to show.
    await asyncio.sleep(0)


app.register_health_check(healthy)

asyncio.run(app.run(13551))
