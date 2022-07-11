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

from email import message
import time
import logging
import requests
import os

logging.basicConfig(level=logging.INFO)

base_url = os.getenv('BASE_URL', 'http://localhost') + ':' + os.getenv(
                    'DAPR_HTTP_PORT', '3500')
PUBSUB_NAME = 'pubsub'
TOPIC = 'mytopic'
ACTORTYPE = 'fakeActorType'

logging.info('Publishing to baseURL: %s, Pubsub Name: %s, Topic: %s' % (
            base_url, PUBSUB_NAME, TOPIC))

for i in range(3):
    message = {'message': 'Hello message'}
    actorid = f'Actor{i}'
    # Publish an event/message using Dapr PubSub via HTTP Post
    result = requests.post(
        url='%s/v1.0/actors/%s/%s/publish/%s/%s' % (base_url, ACTORTYPE, actorid, PUBSUB_NAME, TOPIC),
        json=message
    )
    print(message, flush=True)

    time.sleep(1)