# ------------------------------------------------------------
# Copyright 2022 The Dapr Authors
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
import logging
from flask_dapr import DaprApp
from flask import Flask, request

from time import sleep
import json
from cloudevents.sdk.event import v1
from dapr.ext.grpc import App
from dapr.clients.grpc._response import TopicEventResponse
from dapr.proto import appcallback_v1

app = App()

@app.subscribe(pubsub_name='pubsub', topic='mytopic')
def mytopic(event: v1.Event) -> TopicEventResponse:
    data = json.loads(event.Data())
    print(f'Just checking: Actortype: {data["ActorType"]}, ActorID: {data["ActorID"]}')
    print(f'Subscriber received: id={data["id"]}, message="{data["message"]}", '
          f'content_type="{event.content_type}"', flush=True)
    return "test",200

if __name__ == '__main__':
  app.run(50051)