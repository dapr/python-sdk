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
import argparse
import json
import time

from dapr.clients import DaprClient

parser = argparse.ArgumentParser(description='Publish events to a Dapr pub/sub topic.')
parser.add_argument('--topic', type=str, required=True, help='The topic name to publish to.')
args = parser.parse_args()

topic_name = args.topic

with DaprClient() as d:
    id = 0
    while id < 5:
        id += 1
        req_data = {'id': id, 'message': 'hello world'}

        # Create a typed message with content type and body
        resp = d.publish_event(
            pubsub_name='pubsub',
            topic_name=topic_name,
            data=json.dumps(req_data),
            data_content_type='application/json',
            publish_metadata={'ttlInSeconds': '100', 'rawPayload': 'false'},
        )

        # Print the request
        print(req_data, flush=True)

        time.sleep(1)
