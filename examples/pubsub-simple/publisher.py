# ------------------------------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------------------------------

import json
import time

from dapr import DaprClient

with DaprClient() as d:
    id=0
    while True:
        id+=1
        req_data = {
            'id': id,
            'message': 'hello world'
        }

        # Create a typed message with content type and body
        resp = d.publish_event(
            'TOPIC_A',
            data=json.dumps(req_data),
        )

        # Print the request
        print(req_data, flush=True)
        time.sleep(2)
