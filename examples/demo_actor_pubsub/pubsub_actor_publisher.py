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
    while id < 2:
        id += 1
        req_data = {
            'id': str(id),
            'message': f'Hello {id} times',
        }

        # Create a typed message to call actor type: DemoActor actor
        resp = d.publish_actor_event(
            pubsub_name='pubsub',
            topic_name='mytopic',
            actor_id= '1000',
            actor_type='DemoActor',
            data=json.dumps(req_data),
            data_content_type='application/json',
        )

        # Print the request
        print(req_data, flush=True)

        time.sleep(2)

    while id < 4:
        id += 1
        req_data = {
            'id': str(id),
            'message': f'Hello {id} times',
        }

        # Create a typed message to call actor type: AnotherActor
        resp = d.publish_actor_event(
            pubsub_name='pubsub',
            topic_name='mytopic',
            actor_id= '1000',
            actor_type='AnotherActor',
            data=json.dumps(req_data),
            data_content_type='application/json',
        )

        # Print the request
        print(req_data, flush=True)

        time.sleep(2)

    id += 1
    req_data = {
        'id': str(id),
        'message': f'Hello {id} times',
    }

    # Create a typed message to call actor type: DemoActor with no ID
    resp = d.publish_actor_event(
        pubsub_name='pubsub',
        topic_name='mytopic2',
        actor_id= '',
        actor_type='DemoActor',
        data=json.dumps(req_data),
        data_content_type='application/json',
    )

    # Print the request
    print(req_data, flush=True)

    