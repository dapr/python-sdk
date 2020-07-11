import json
import time

from dapr import DaprClient

with DaprClient() as d:
    n = 0
    while True:
        n += 1
        req_data = {
            'id': n,
            'message': 'hello world'
        }
        metadata = (('content-type', 'json'),)
        print(req_data, flush=True)

        # Create a typed message with content type and body
        resp = d.invoke_binding('kafkaBinding', 'create', json.dumps(req_data), metadata)

        time.sleep(1)
