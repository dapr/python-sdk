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

import json
import time

from dapr.clients import DaprClient

with DaprClient() as d:
    id = 0
    while id < 3:
        id += 1
        req_data = {'id': id, 'message': 'hello world'}

        # Create a typed message with content type and body
        resp = d.publish_event(
            pubsub_name='pubsub',
            topic_name='TOPIC_A',
            data=json.dumps(req_data),
            data_content_type='application/json',
        )

        # Print the request
        print(req_data, flush=True)

        time.sleep(1)

    # we can publish events to different topics but handle them with the same method
    # by disabling topic validation in the subscriber

    id = 3
    while id < 6:
        id += 1
        req_data = {'id': id, 'message': 'hello world'}
        resp = d.publish_event(
            pubsub_name='pubsub',
            topic_name=f'topic/{id}',
            data=json.dumps(req_data),
            data_content_type='application/json',
        )

        # Print the request
        print(req_data, flush=True)

        time.sleep(0.5)

    # This topic will fail - initiate a retry which gets routed to the dead letter topic
    req_data['id'] = 7
    resp = d.publish_event(
        pubsub_name='pubsub',
        topic_name='TOPIC_D',
        data=json.dumps(req_data),
        data_content_type='application/json',
        publish_metadata={'custommeta': 'somevalue'},
    )

    # Print the request
    print(req_data, flush=True)
